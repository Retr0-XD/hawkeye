"""Audit collector (Layer 1, operation 4).

Reads Cloud Audit Logs exported to BigQuery (last 24h) and normalizes them into
:class:`AuditEvent`. If the export is not configured, logs a warning and returns
[] (optional, user-configured prerequisite).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List
from uuid import uuid4

from ..config import get_settings
from ..gcp_clients import get_bigquery_client
from ..models import AuditEvent

logger = logging.getLogger("hawkeye.ingestion.collectors.audit")


async def collect_audit(project_id: str, hours: int = 24) -> List[AuditEvent]:
    settings = get_settings()
    if not settings.audit_bq_dataset or not settings.audit_bq_table:
        logger.warning(
            "Audit log export not configured (HAWKEYE_AUDIT_BQ_DATASET/TABLE). "
            "Skipping audit collection. Configure Cloud Audit Logs -> BigQuery export."
        )
        return []

    client = get_bigquery_client()
    table = f"`{settings.gcp_project_id}.{settings.audit_bq_dataset}.{settings.audit_bq_table}`"
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S")

    query = f"""
        SELECT
            timestamp,
            protopayload_auditlog.authenticationInfo.principalEmail AS user_email,
            protopayload_auditlog.requestMetadata.callerIp AS user_ip,
            protopayload_auditlog.methodName AS action,
            protopayload_auditlog.resourceName AS resource_id,
            protopayload_auditlog.status.code AS status_code
        FROM {table}
        WHERE timestamp >= TIMESTAMP('{since}')
          AND resource.labels.project_id = @project_id
        ORDER BY timestamp DESC
        LIMIT 5000
    """
    from google.cloud.bigquery import ScalarQueryParameter

    params = [ScalarQueryParameter("project_id", "STRING", project_id)]
    from google.cloud.bigquery import QueryJobConfig

    out: List[AuditEvent] = []
    try:
        loop = __import__("asyncio").get_event_loop()
        rows = await loop.run_in_executor(
            None,
            lambda: list(client.query(query, job_config=QueryJobConfig(query_parameters=params)).result()),
        )
        for row in rows:
            ts = row.get("timestamp")
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            out.append(
                AuditEvent(
                    id=str(uuid4()),
                    timestamp=ts or datetime.now(timezone.utc),
                    user_email=row.get("user_email"),
                    user_ip=row.get("user_ip"),
                    action=(row.get("action") or "UNKNOWN").split(".")[-1].upper(),
                    resource_id=row.get("resource_id"),
                    status="FAILURE" if (row.get("status_code") or 0) != 0 else "SUCCESS",
                )
            )
    except Exception as exc:  # noqa: BLE001
        logger.error("Audit query failed for %s: %s", project_id, exc)
        return []
    logger.info("Collected %d audit events for %s", len(out), project_id)
    return out
