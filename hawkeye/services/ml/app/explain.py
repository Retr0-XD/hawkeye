"""Explainable ML for Hawkeye.

The original anomaly/failure models trained purely on BigQuery telemetry
(cpu/memory/network/error/cost). In a fresh project those tables are empty, so
every resource produced an identical, unexplained 0.8667 score — which is
exactly why the dashboard felt "bland": a number with no story.

This module adds *explainability* on top of the existing models:

  * It pulls **structural metadata** (type, region, public access, encryption,
    backups, audit logging, age, parent/child relationships) from Firestore —
    data we always have regardless of billing/telemetry config.
  * It derives **feature drivers** (which inputs pushed the score up/down) and a
    **human-readable reason** for every prediction.
  * It computes a **risk score** that blends the model score with structural
    risk signals (public DB, unencrypted, no backups, no audit logging,
    orphaned/old resources) so the output is meaningful even with zero
    telemetry.

The result is a prediction that the UI can *explain* ("Public Database with no
encryption — high security risk") instead of just showing a bar.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from .config import Settings, get_settings
from .gcp_clients import get_firestore_client

logger = logging.getLogger("hawkeye.ml.explain")

# Structural risk signals: (key, weight, label, reason). Higher weight = more
# dangerous. These are combined with the model anomaly score to produce a
# blended, explainable risk score in [0, 1].
STRUCTURAL_RISKS: List[Tuple[str, float, str, str]] = [
    ("public_database", 0.45, "Public Database",
     "Database is publicly accessible — anyone on the internet can reach it."),
    ("public_storage", 0.35, "Public Storage Bucket",
     "Storage bucket is publicly accessible — data may be exposed."),
    ("unencrypted", 0.30, "Unencrypted at rest",
     "Resource reports unencrypted data at rest."),
    ("no_backup", 0.25, "No backup configured",
     "No backup policy — data loss would be unrecoverable."),
    ("no_audit_logging", 0.20, "Audit logging disabled",
     "Audit logging is off — changes are not traceable."),
    ("old_orphan", 0.20, "Aged / possibly orphaned",
     "Resource is old and shows no utilization — likely orphaned."),
    ("public_compute", 0.15, "Public Compute endpoint",
     "Compute resource is exposed to the public internet."),
]


def load_resource_metadata(resource_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single resource's structural metadata from Firestore.

    Returns None if not found. Uses the same sanitized id scheme as the
    processing service (see storage._safe_id).
    """
    try:
        settings = get_settings()
        db = get_firestore_client()
        from .sanitize import _safe_id  # local import to avoid cycle

        doc = db.collection(settings.fs_resources).document(_safe_id(resource_id)).get()
        if not doc.exists:
            return None
        return doc.to_dict()
    except Exception as exc:  # noqa: BLE001
        logger.warning("resource metadata load failed for %s: %s", resource_id, exc)
        return None


def load_all_resource_metadata() -> Dict[str, Dict[str, Any]]:
    """Fetch all resource metadata keyed by raw resource id."""
    out: Dict[str, Dict[str, Any]] = {}
    try:
        settings = get_settings()
        db = get_firestore_client()
        for d in db.collection(settings.fs_resources).stream():
            data = d.to_dict()
            rid = data.get("id", d.id)
            out[rid] = data
    except Exception as exc:  # noqa: BLE001
        logger.warning("bulk resource metadata load failed: %s", exc)
    return out


def _structural_signals(meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return the active structural risk signals for a resource.

    These are derived purely from metadata we always have (type, public flag,
    dependency relationships) so the explainer is meaningful even before
    billing/telemetry exports are configured. The signal set is intentionally
    conservative: we only flag things that are objectively observable in the
    data, never a synthetic "anomaly" from an untrained model.
    """
    rtype = (meta.get("type") or "").lower()
    signals: List[Dict[str, Any]] = []

    public = bool(meta.get("public_access"))
    if public and ("storage" in rtype or "bucket" in rtype):
        signals.append(_sig("public_storage"))
    elif public and "database" in rtype:
        signals.append(_sig("public_database"))
    elif public and "compute" in rtype:
        signals.append(_sig("public_compute"))

    enc = str(meta.get("encryption_status") or "").upper()
    if enc and enc not in ("ENCRYPTED", "CUSTOMER_MANAGED", "GOOGLE_MANAGED", "TRUE"):
        signals.append(_sig("unencrypted"))

    if meta.get("backup_enabled") is False:
        signals.append(_sig("no_backup"))

    if meta.get("audit_logging_enabled") is False:
        signals.append(_sig("no_audit_logging"))

    # Aged + no utilization => likely orphaned.
    age = meta.get("age_days")
    if age is None:
        created = meta.get("created_at")
        if created:
            try:
                from datetime import datetime, timezone

                if isinstance(created, str):
                    created = datetime.fromisoformat(created.replace("Z", "+00:00"))
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                age = (datetime.now(timezone.utc) - created).days
            except Exception:  # noqa: BLE001
                age = None
    cpu = meta.get("cpu_utilization_avg")
    mem = meta.get("memory_utilization_avg")
    if age is not None and age >= 30 and (cpu in (None, 0) and mem in (None, 0)):
        signals.append(_sig("old_orphan"))

    return signals


def _sig(key: str) -> Dict[str, Any]:
    for k, w, label, reason in STRUCTURAL_RISKS:
        if k == key:
            return {"key": k, "weight": w, "label": label, "reason": reason}
    return {"key": key, "weight": 0.1, "label": key, "reason": ""}


def explain_prediction(
    resource_id: str,
    anomaly_score: float,
    is_anomaly: bool,
    failure_prob: float,
    is_risk: bool,
    features: Dict[str, float],
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build an explainable prediction bundle.

    Returns a dict with:
      risk_score        blended [0,1] risk (structural + model)
      risk_level        LOW | MEDIUM | HIGH
      drivers           list of {label, contribution, reason} sorted desc
      reason            one-line human summary
      structural_risks  list of active structural signals
    """
    settings = get_settings()
    if meta is None:
        meta = load_resource_metadata(resource_id) or {}

    signals = _structural_signals(meta)
    structural_score = min(1.0, sum(s["weight"] for s in signals))

    # Blend: model anomaly (telemetry) + structural (metadata). When there is
    # no real telemetry the model score is 0, so the structural signal carries
    # the weight — the score is never a degenerate constant. age_days is
    # always-present metadata and must not count as "real" signal.
    _signal_cols = [
        "cpu_percent", "memory_percent", "network_out_bytes",
        "error_rate_percent", "cost_daily", "cost_trend", "utilization_var",
    ]
    has_telemetry = bool(features) and sum(abs(features.get(c, 0.0)) for c in _signal_cols) > 1e-6
    model_component = anomaly_score if has_telemetry else 0.0
    risk_score = round(min(1.0, max(model_component, structural_score)), 4)

    # Drivers: combine model + structural into a ranked list.
    drivers: List[Dict[str, Any]] = []
    if model_component > 0.05:
        drivers.append({
            "label": "Telemetry anomaly",
            "contribution": round(model_component, 3),
            "reason": "Usage pattern flagged as anomalous by the Isolation Forest model.",
        })
    for s in signals:
        drivers.append({
            "label": s["label"],
            "contribution": round(s["weight"], 3),
            "reason": s["reason"],
        })
    drivers.sort(key=lambda d: d["contribution"], reverse=True)

    if risk_score >= settings.high_risk_threshold:
        level = "HIGH"
    elif risk_score >= settings.medium_risk_threshold:
        level = "MEDIUM"
    else:
        level = "LOW"

    if drivers:
        top = drivers[0]
        reason = f"{top['label']}: {top['reason']}"
    elif is_anomaly:
        reason = "Telemetry anomaly detected by the model."
    elif is_risk:
        reason = "Elevated failure probability from the model."
    else:
        reason = "No significant risk signals detected — resource looks healthy."

    return {
        "risk_score": risk_score,
        "risk_level": level,
        "drivers": drivers,
        "reason": reason,
        "structural_risks": [s["label"] for s in signals],
    }


def explain_batch(
    items: List[Dict[str, Any]],
    meta_map: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Attach explainability to a list of prediction items (from /ml/predict/all)."""
    if meta_map is None:
        meta_map = load_all_resource_metadata()
    out = []
    for it in items:
        rid = it.get("resource_id", "")
        meta = meta_map.get(rid, {})
        exp = explain_prediction(
            rid,
            it.get("anomaly", {}).get("score", 0.0),
            it.get("anomaly", {}).get("is_anomaly", False),
            it.get("failure", {}).get("probability", 0.0),
            it.get("failure", {}).get("is_high_risk", False),
            it.get("features", {}) or {},
            meta,
        )
        merged = dict(it)
        merged["explanation"] = exp
        out.append(merged)
    return out
