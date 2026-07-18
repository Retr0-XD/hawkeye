"""Billing collector (Layer 1, operation 2).

Reads the Cloud Billing Export -> BigQuery table (daily cost per resource)
and normalizes rows into :class:`BillingRecord`. If the export dataset/table
is not configured, the collector logs a clear warning and returns [] (no stub,
just optional - the export is a user-configured prerequisite).
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Dict, List

from ..config import get_settings
from ..gcp_clients import get_bigquery_client
from ..models import BillingRecord

logger = logging.getLogger("hawkeye.ingestion.collectors.billing")


def _today() -> str:
    return date.today().strftime("%Y-%m-%d")


async def collect_billing(project_id: str, day: str | None = None) -> List[BillingRecord]:
    settings = get_settings()
    if not settings.billing_bq_dataset or not settings.billing_bq_table:
        logger.warning(
            "Billing export not configured (HAWKEYE_BILLING_BQ_DATASET/TABLE). "
            "Skipping billing collection. Configure Cloud Billing Export to BigQuery."
        )
        return []

    day = day or _today()
    client = get_bigquery_client()
    table = f"`{settings.gcp_project_id}.{settings.billing_bq_dataset}.{settings.billing_bq_table}`"

    # Cloud Billing Export (standard/finops) columns vary; we query the common
    # ones and gracefully tolerate missing columns.
    query = f"""
        SELECT
            COALESCE(project.id, project_name, '') AS project_id,
            COALESCE(service.description, '') AS service,
            COALESCE(sku.description, '') AS sku,
            COALESCE(system_labels, CAST([] AS STRING)) AS system_labels,
            COALESCE(labels, CAST([] AS STRING)) AS labels,
            SUM(cost) AS cost
        FROM {table}
        WHERE DATE(_PARTITIONTIME) = '{day}'
          AND COALESCE(project.id, '') = @project_id
        GROUP BY project_id, service, sku, system_labels, labels
    """

    from google.cloud.bigquery import ScalarQueryParameter

    job_config_params = [ScalarQueryParameter("project_id", "STRING", project_id)]

    records: Dict[str, BillingRecord] = {}
    try:
        loop = __import__("asyncio").get_event_loop()
        rows = await loop.run_in_executor(
            None,
            lambda: list(client.query(query, job_config=__mk_job_config(job_config_params)).result()),
        )
        for row in rows:
            # Derive a stable resource id from system labels (gcp resource id).
            rid = _resource_id_from_labels(row.get("system_labels"), row.get("labels"), project_id)
            if not rid:
                continue
            rec = records.setdefault(
                rid,
                BillingRecord(resource_id=rid, date=day),
            )
            sku = row.get("sku") or row.get("service") or "other"
            rec.sku[sku] = rec.sku.get(sku, 0.0) + float(row.get("cost") or 0.0)
            rec.daily_cost += float(row.get("cost") or 0.0)
    except Exception as exc:  # noqa: BLE001
        logger.error("Billing query failed for %s: %s", project_id, exc)
        return []

    for rec in records.values():
        rec.month_to_date = rec.daily_cost  # aggregated downstream by processing svc
    logger.info("Collected %d billing records for %s on %s", len(records), project_id, day)
    return list(records.values())


def __mk_job_config(params):
    from google.cloud.bigquery import QueryJobConfig

    return QueryJobConfig(query_parameters=params)


def _resource_id_from_labels(system_labels: str, labels: str, project_id: str) -> str | None:
    """Extract a Hawkeye resource id from billing export labels.

    Cloud Billing Export includes ``system_labels`` such as
    ``{"compute.googleapis.com/resource_id": "12345", ...}`` and
    ``labels`` (user labels). We prefer the resource_id system label.
    """
    import json

    for raw in (system_labels, labels):
        if not raw:
            continue
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            continue
        if isinstance(data, dict):
            rid = data.get("compute.googleapis.com/resource_id")
            if rid:
                return f"gcp://compute/{project_id}/{rid}"
            name = data.get("compute.googleapis.com/resource_name")
            if name:
                return f"gcp://compute/{project_id}/{name}"
    return None
