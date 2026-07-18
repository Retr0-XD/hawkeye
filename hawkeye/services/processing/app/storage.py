"""Storage operations (Layer 2, operation 6).

Batch-writes enriched resources + recommendations to Firestore and streams
metric / billing / audit / lifecycle rows to BigQuery. Idempotent: documents
are keyed by stable ids, so reprocessing yields the same result.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List

from .config import Settings, get_settings
from .gcp_clients import get_bigquery_client, get_firestore_client
from .models import Alert, AuditEvent, BillingRecord, MetricRecord, Recommendation, Resource

logger = logging.getLogger("hawkeye.processing.storage")


def _clear_collection(db, collection_name: str, batch_size: int = 400) -> None:
    """Delete all documents in a collection (used for full-regeneration sets)."""
    docs = list(db.collection(collection_name).list_documents())
    if not docs:
        return
    for i in range(0, len(docs), batch_size):
        batch = db.batch()
        for doc in docs[i : i + batch_size]:
            batch.delete(doc)
        batch.commit()


def _safe_id(raw_id: str) -> str:
    """Firestore document ids cannot contain '/' or '.' in a way that breaks
    the path. Replace path separators with a safe token."""
    return raw_id.replace("/", "__").replace(".", "_dot_")


def write_firestore(
    resources: Dict[str, Resource],
    recommendations: List[Recommendation],
    graph: Dict[str, List[str]],
    new_ids: List[str],
    deleted_ids: List[str],
    alerts: List["Alert"] = None,
) -> None:
    settings = get_settings()
    db = get_firestore_client()

    # Recommendations and alerts are fully regenerated each cycle, so clear
    # the previous set before rewriting (avoids unbounded accumulation across
    # runs). Resources are upserted by id (not cleared) to preserve history.
    _clear_collection(db, settings.fs_recommendations)
    if alerts:
        _clear_collection(db, settings.fs_alerts)

    # Batch resource docs.
    batch = db.batch()
    count = 0
    for rid, res in resources.items():
        doc_ref = db.collection(settings.fs_resources).document(_safe_id(rid))
        data = res.model_dump(mode="json")
        # Firestore can't store None timestamps as datetime; keep as-is.
        batch.set(doc_ref, data)
        count += 1
        if count >= 400:  # Firestore batch limit is 500.
            batch.commit()
            batch = db.batch()
            count = 0
    if count:
        batch.commit()

    # Recommendations.
    rbatch = db.batch()
    rcount = 0
    for rec in recommendations:
        # Recommendation ids embed resource ids (which contain '/'), so they
        # must be sanitized before use as a Firestore document key.
        ref = db.collection(settings.fs_recommendations).document(_safe_id(rec.id))
        rbatch.set(ref, rec.model_dump(mode="json"))
        rcount += 1
        if rcount >= 400:
            rbatch.commit()
            rbatch = db.batch()
            rcount = 0
    if rcount:
        rbatch.commit()

    # Alerts (lifecycle changes).
    if alerts:
        abatch = db.batch()
        acount = 0
        for alert in alerts:
            aref = db.collection(settings.fs_alerts).document(alert.id)
            abatch.set(aref, alert.model_dump(mode="json"))
            acount += 1
            if acount >= 400:
                abatch.commit()
                abatch = db.batch()
                acount = 0
        if acount:
            abatch.commit()

    # Dependency graph (single doc).
    db.collection(settings.fs_graph).document("current").set(
        {"edges": graph, "updated_at": datetime.now(timezone.utc)}
    )

    # Lifecycle change markers.
    if new_ids or deleted_ids:
        life_ref = db.collection(settings.fs_state).document("last_changes")
        life_ref.set(
            {
                "new": new_ids,
                "deleted": deleted_ids,
                "detected_at": datetime.now(timezone.utc),
            }
        )
    logger.info(
        "Firestore write: %d resources, %d recommendations, graph=%d nodes",
        len(resources), len(recommendations), len(graph),
    )


def _bq_rows_metrics(metrics: List[MetricRecord], settings: Settings) -> List[dict]:
    rows = []
    for m in metrics:
        d = m.model_dump(mode="json")
        d["project_id"] = settings.gcp_project_id
        rows.append(d)
    return rows


def _bq_rows_billing(billing: List[BillingRecord], settings: Settings) -> List[dict]:
    rows = []
    for b in billing:
        d = b.model_dump(mode="json")
        # BigQuery schema defines `sku` as STRING; serialize the dict to JSON.
        d["sku"] = json.dumps(b.sku) if b.sku else "{}"
        d["project_id"] = settings.gcp_project_id
        rows.append(d)
    return rows


def _bq_rows_audit(audit: List[AuditEvent], settings: Settings) -> List[dict]:
    rows = []
    for a in audit:
        d = a.model_dump(mode="json")
        # BigQuery schema defines `changes` as STRING; serialize the dict to JSON.
        d["changes"] = json.dumps(a.changes) if a.changes else "{}"
        d["project_id"] = settings.gcp_project_id
        rows.append(d)
    return rows


def _bq_rows_lifecycle(
    new_ids: List[str], deleted_ids: List[str], settings: Settings
) -> List[dict]:
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for rid in new_ids:
        rows.append({"resource_id": rid, "event": "CREATED", "timestamp": now,
                     "project_id": settings.gcp_project_id})
    for rid in deleted_ids:
        rows.append({"resource_id": rid, "event": "DELETED", "timestamp": now,
                     "project_id": settings.gcp_project_id})
    return rows


def write_bigquery(
    metrics: List[MetricRecord],
    billing: List[BillingRecord],
    audit: List[AuditEvent],
    new_ids: List[str],
    deleted_ids: List[str],
) -> None:
    settings = get_settings()
    client = get_bigquery_client()
    ds = settings.bq_dataset

    # Raise on any insert error so the orchestrator does NOT ack messages that
    # were lost (the previous swallow-and-ack behavior caused silent data loss).
    def _insert(table: str, rows: list) -> None:
        if not rows:
            return
        errors = client.insert_rows_json(table, rows)
        if errors:
            raise RuntimeError(f"BigQuery insert failed for {table}: {errors[:3]}")

    if metrics:
        _insert(f"{settings.gcp_project_id}.{ds}.{settings.bq_metrics_table}",
                _bq_rows_metrics(metrics, settings))
    if billing:
        _insert(f"{settings.gcp_project_id}.{ds}.{settings.bq_billing_table}",
                _bq_rows_billing(billing, settings))
    if audit:
        _insert(f"{settings.gcp_project_id}.{ds}.{settings.bq_audit_table}",
                _bq_rows_audit(audit, settings))
    life_rows = _bq_rows_lifecycle(new_ids, deleted_ids, settings)
    if life_rows:
        _insert(f"{settings.gcp_project_id}.{ds}.{settings.bq_lifecycle_table}", life_rows)
    logger.info(
        "BigQuery write: %d metrics, %d billing, %d audit, %d lifecycle",
        len(metrics), len(billing), len(audit), len(life_rows),
    )
