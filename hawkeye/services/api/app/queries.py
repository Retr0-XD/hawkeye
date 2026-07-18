"""Query layer (Layer 5): read processed data from Firestore + BigQuery.

Pure read functions used by the REST endpoints. All return plain dicts so
FastAPI can serialize them directly.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter

from .config import Settings, get_settings
from .gcp_clients import get_bigquery_client, get_firestore_client

logger = logging.getLogger("hawkeye.api.queries")


def _json_safe(doc) -> dict:
    """Make a Firestore document JSON-serializable (DatetimeWithNanoseconds)."""
    data = doc.to_dict()
    out = {}
    for k, v in data.items():
        if hasattr(v, "timestamp"):  # DatetimeWithNanoseconds
            out[k] = str(v)
        elif isinstance(v, dict):
            out[k] = {kk: (str(vv) if hasattr(vv, "timestamp") else vv) for kk, vv in v.items()}
        else:
            out[k] = v
    # Prefer the raw stored resource id (e.g. gcp://compute/...) over the
    # Firestore-sanitized document id, so API and ML agree on id format.
    out["id"] = data.get("id", doc.id)
    return out


def list_resources(
    limit: int = 50,
    offset: int = 0,
    resource_type: Optional[str] = None,
    status: Optional[str] = None,
    public_only: bool = False,
) -> Dict:
    settings = get_settings()
    db = get_firestore_client()
    col = db.collection(settings.fs_resources)
    query = col
    if resource_type:
        query = query.where("type", "==", resource_type)
    if status:
        query = query.where("status", "==", status)
    if public_only:
        query = query.where("public_access", "==", True)

    # Total count (cheap-ish for MVP scale).
    total = sum(1 for _ in col.stream())
    docs = query.offset(offset).limit(limit).stream()
    items = [_json_safe(d) for d in docs]
    return {
        "items": items,
        "pageInfo": {
            "totalCount": total,
            "hasNextPage": (offset + limit) < total,
            "limit": limit,
            "offset": offset,
        },
    }


def get_resource(resource_id: str) -> Optional[dict]:
    settings = get_settings()
    db = get_firestore_client()
    # Document ids are sanitized (see processing storage._safe_id).
    from .sanitize import _safe_id

    doc = db.collection(settings.fs_resources).document(_safe_id(resource_id)).get()
    if not doc.exists:
        return None
    return _json_safe(doc)


def list_recommendations(
    limit: int = 50, rec_type: Optional[str] = None, severity: Optional[str] = None
) -> Dict:
    settings = get_settings()
    db = get_firestore_client()
    col = db.collection(settings.fs_recommendations)
    query = col
    if rec_type:
        query = query.where("type", "==", rec_type)
    if severity:
        query = query.where("severity", "==", severity)
    docs = query.limit(limit).stream()
    items = [_json_safe(d) for d in docs]
    total_savings = sum(float(i.get("estimated_savings", 0) or 0) for i in items)
    return {"items": items, "totalEstimatedSavings": round(total_savings, 2)}


def list_alerts(limit: int = 50) -> Dict:
    settings = get_settings()
    db = get_firestore_client()
    docs = db.collection(settings.fs_alerts).limit(limit).stream()
    return {"items": [_json_safe(d) for d in docs]}


def get_graph() -> dict:
    settings = get_settings()
    db = get_firestore_client()
    doc = db.collection(settings.fs_graph).document("current").get()
    if not doc.exists:
        return {"edges": {}}
    data = _json_safe(doc)
    return {"edges": data.get("edges", {}), "updated_at": data.get("updated_at")}


def dashboard_summary() -> dict:
    """Aggregate counts/costs for the demo dashboard."""
    settings = get_settings()
    db = get_firestore_client()
    resources = list(db.collection(settings.fs_resources).stream())
    recs = list(db.collection(settings.fs_recommendations).stream())

    by_type: Dict[str, int] = {}
    total_monthly_cost = 0.0
    public_count = 0
    unused_count = 0
    for d in resources:
        r = d.to_dict()
        t = r.get("type", "Unknown")
        by_type[t] = by_type.get(t, 0) + 1
        total_monthly_cost += float(r.get("monthly_cost_projection", 0) or 0)
        if r.get("public_access"):
            public_count += 1
        if (r.get("monthly_cost_projection", 0) or 0) > 0 and (
            r.get("cpu_utilization_avg") in (None, 0)
            or r.get("cpu_utilization_avg", 100) < 5
        ):
            unused_count += 1

    total_savings = sum(float(r.to_dict().get("estimated_savings", 0) or 0) for r in recs)
    return {
        "resourceCount": len(resources),
        "byType": by_type,
        "totalMonthlyCostProjection": round(total_monthly_cost, 2),
        "publicResources": public_count,
        "unusedResources": unused_count,
        "recommendationCount": len(recs),
        "totalEstimatedSavings": round(total_savings, 2),
    }


def recent_metrics(resource_id: Optional[str], limit: int = 100) -> List[dict]:
    settings = get_settings()
    client = get_bigquery_client()
    table = f"`{settings.gcp_project_id}.{settings.bq_dataset}.{settings.bq_metrics_table}`"
    # Use parameterized queries to avoid SQL injection via resource_id.
    from google.cloud.bigquery import ScalarQueryParameter

    params = [ScalarQueryParameter("lim", "INT64", limit)]
    if resource_id:
        where = "WHERE resource_id = @rid"
        params.append(ScalarQueryParameter("rid", "STRING", resource_id))
    else:
        where = ""
    sql = (
        f"SELECT resource_id, timestamp, cpu_percent_avg, memory_percent, "
        f"network_out_bytes FROM {table} {where} "
        f"ORDER BY timestamp DESC LIMIT @lim"
    )
    job_config = QueryJobConfig(query_parameters=params)
    rows = client.query(sql, job_config=job_config).result()
    return [dict(r) for r in rows]


def cost_trend(days: int = 30) -> List[dict]:
    """Daily total cost trend from BigQuery billing table (if export enabled)."""
    settings = get_settings()
    client = get_bigquery_client()
    table = f"`{settings.gcp_project_id}.{settings.bq_dataset}.{settings.bq_billing_table}`"
    sql = (
        f"SELECT date, SUM(daily_cost) AS total_cost FROM {table} "
        f"GROUP BY date ORDER BY date DESC LIMIT {days}"
    )
    try:
        rows = client.query(sql).result()
        return [dict(r) for r in rows]
    except Exception as exc:  # noqa: BLE001
        logger.warning("cost_trend query failed (billing export not configured?): %s", exc)
        return []


def ml_predictions() -> Dict:
    """Fetch ML predictions (anomaly / failure / cost) from the ML service.

    Calls the Layer 4 ML service's /ml/predict/all endpoint. Degrades to an
    empty result if the service is unreachable so the API never hard-fails.
    """
    import urllib.request
    import json as _json

    settings = get_settings()
    url = f"{settings.ml_service_url.rstrip('/')}/ml/predict/all"
    try:
        req = urllib.request.Request(url, method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return _json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("ml_predictions call failed: %s", exc)
        return {"scored": 0, "total_resources": 0, "anomalies": [], "failure_risks": [], "high_risk": [], "items": []}


def smart_insights() -> Dict:
    """Aggregate a smart, explainable insights view for the dashboard.

    Combines recommendations, compliance posture, ML risk ranking and the
    dependency graph into a single prioritized "what to do next" payload. This
    is the brain behind the Smart Insights tab — it turns raw scores into
    ranked, actionable items with reasons.
    """
    settings = get_settings()
    db = get_firestore_client()

    # Recommendations (already ranked by severity/savings in processing).
    recs = [_json_safe(d) for d in db.collection(settings.fs_recommendations).stream()]

    # ML risk ranking.
    preds = ml_predictions()
    risk_items = []
    for it in preds.get("items", []):
        exp = it.get("explanation") or {}
        risk_items.append({
            "resource_id": it.get("resource_id"),
            "risk_score": exp.get("risk_score", 0.0),
            "risk_level": exp.get("risk_level", "LOW"),
            "reason": exp.get("reason", ""),
            "drivers": exp.get("drivers", []),
            "anomaly": it.get("anomaly", {}),
            "failure": it.get("failure", {}),
        })
    risk_items.sort(key=lambda r: r["risk_score"], reverse=True)

    # Compliance posture.
    comp = compliance_summary()

    # Graph (for blast-radius context).
    graph = get_graph()
    edges = graph.get("edges", {}) or {}
    # Count dependents per node (blast radius).
    dependents: Dict[str, int] = {}
    for src, targets in edges.items():
        for t in targets:
            dependents[t] = dependents.get(t, 0) + 1

    # Build prioritized insight cards.
    insights = []
    for r in risk_items:
        if r["risk_level"] == "HIGH":
            insights.append({
                "kind": "risk",
                "level": r["risk_level"],
                "resource_id": r["resource_id"],
                "title": f"High risk: {r['resource_id'].split('/')[-1]}",
                "detail": r["reason"],
                "drivers": r["drivers"],
                "blast_radius": dependents.get(r["resource_id"], 0),
            })
    for rec in recs:
        insights.append({
            "kind": "recommendation",
            "level": (rec.get("severity") or "LOW"),
            "resource_id": rec.get("resource_id"),
            "title": rec.get("title", "Recommendation"),
            "detail": rec.get("description", ""),
            "savings": rec.get("estimated_savings", 0.0),
            "blast_radius": dependents.get(rec.get("resource_id", ""), 0),
        })
    # Compliance insight if score is low.
    if comp.get("score", 100) < 90:
        insights.append({
            "kind": "compliance",
            "level": "HIGH" if comp.get("score", 100) < 70 else "MEDIUM",
            "resource_id": None,
            "title": f"Compliance score {comp.get('score')}/100",
            "detail": (
                f"{comp.get('violations', 0)} policy violations across "
                f"{comp.get('total', 0)} resources."
            ),
            "savings": 0.0,
            "blast_radius": 0,
        })

    # Sort: HIGH first, then by savings/blast radius.
    level_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    insights.sort(
        key=lambda i: (level_rank.get(i["level"], 3), i.get("savings", 0) or 0, i.get("blast_radius", 0)),
        reverse=False,
    )

    return {
        "insights": insights,
        "risk_ranking": risk_items,
        "compliance": comp,
        "total_estimated_savings": round(
            sum(float(r.get("savings", 0) or 0) for r in insights), 2
        ),
        "high_risk_count": sum(1 for i in insights if i["level"] == "HIGH"),
    }


def cost_breakdown() -> Dict:
    """Cost projection grouped by resource type for the Cost dashboard."""
    settings = get_settings()
    db = get_firestore_client()
    resources = list(db.collection(settings.fs_resources).stream())
    by_type: Dict[str, float] = {}
    total = 0.0
    for d in resources:
        r = d.to_dict()
        t = r.get("type", "Unknown")
        cost = float(r.get("monthly_cost_projection", 0) or 0)
        by_type[t] = by_type.get(t, 0.0) + cost
        total += cost
    items = [
        {"type": t, "cost": round(c, 2), "pct": round((c / total * 100) if total else 0, 1)}
        for t, c in sorted(by_type.items(), key=lambda kv: kv[1], reverse=True)
    ]
    return {"total": round(total, 2), "items": items}


def compliance_summary() -> Dict:
    """Security/compliance posture derived from resource flags."""
    settings = get_settings()
    db = get_firestore_client()
    resources = list(db.collection(settings.fs_resources).stream())
    public_resources: List[str] = []
    unencrypted: List[str] = []
    no_backup: List[str] = []
    no_audit_logging: List[str] = []
    total = 0
    for d in resources:
        r = d.to_dict()
        total += 1
        rid = r.get("id", d.id)
        if r.get("public_access"):
            public_resources.append(rid)
        enc = r.get("encryption_status")
        if enc and str(enc).upper() not in ("ENCRYPTED", "CUSTOMER_MANAGED", "GOOGLE_MANAGED", "TRUE"):
            unencrypted.append(rid)
        if r.get("backup_enabled") is False:
            no_backup.append(rid)
        if r.get("audit_logging_enabled") is False:
            no_audit_logging.append(rid)
    violations = len(public_resources) + len(unencrypted) + len(no_backup) + len(no_audit_logging)
    score = round(max(0, 100 - (violations / total * 100)) if total else 100, 1)
    return {
        "total": total,
        "score": score,
        "violations": violations,
        "public_resources": public_resources,
        "unencrypted": unencrypted,
        "no_backup": no_backup,
        "no_audit_logging": no_audit_logging,
    }
