"""Metrics collector (Layer 1, operation 3).

Queries Cloud Monitoring for recent time-series of the metrics relevant to each
resource type and normalizes them into :class:`MetricRecord`. Aggregates to a
5-minute window per the architecture doc.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from google.cloud import monitoring_v3

from ..gcp_clients import get_monitoring_client
from ..models import MetricRecord

logger = logging.getLogger("hawkeye.ingestion.collectors.metrics")

# Metric -> (field on MetricRecord, is_float)
METRIC_MAP = {
    "compute.googleapis.com/instance/cpu/utilization": ("cpu_percent", True),
    "compute.googleapis.com/instance/network/received_bytes_count": ("network_in_bytes", False),
    "compute.googleapis.com/instance/network/sent_bytes_count": ("network_out_bytes", False),
    "cloudsql.googleapis.com/database/cpu/utilization": ("cpu_percent", True),
    "cloudsql.googleapis.com/database/memory/utilization": ("memory_percent", True),
    "cloudsql.googleapis.com/database/queries": ("queries_per_second", True),
    "run.googleapis.com/container/cpu/utilizations": ("cpu_percent", True),
    "storage.googleapis.com/api/request_count": ("error_count", False),
}


def _avg(values: List[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def _extract_value(typed_value) -> Optional[float]:
    """Safely read a Monitoring TypedValue regardless of protobuf version."""
    for attr in ("double_value", "int64_value"):
        try:
            val = getattr(typed_value, attr)
            if val is not None:
                return float(val)
        except AttributeError:
            continue
    try:
        dv = typed_value.distribution_value
        if dv is not None:
            return float(dv.mean)
    except AttributeError:
        pass
    return None


async def collect_metrics_for_resource(
    resource: "object", project_id: str, window_minutes: int = 5
) -> Optional[MetricRecord]:
    """Fetch the last ``window_minutes`` of metrics for a single resource."""
    client = get_monitoring_client()
    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=window_minutes)

    rid = getattr(resource, "id", None)
    rtype = getattr(resource, "type", None)
    name_field = getattr(resource, "name", None)
    provider_id = getattr(resource, "provider_id", None)
    if not rid or not name_field:
        return None

    # Build a filter scoping to this resource. Monitoring uses the
    # `resource.labels` (e.g. instance_id for GCE, instance_name for Cloud SQL).
    resource_type_map = {
        "VM": "gce_instance",
        "Database": "cloudsql_database",
        "Container": "cloud_run_revision",
    }
    mon_resource = resource_type_map.get(rtype)
    if not mon_resource:
        return None

    rec = MetricRecord(resource_id=rid, timestamp=now)
    found_any = False
    try:
        loop = asyncio.get_running_loop()
        for metric, (field, is_float) in METRIC_MAP.items():
            if mon_resource not in metric:
                # Only query metrics relevant to this resource type.
                if not metric.startswith(
                    "compute" if mon_resource == "gce_instance" else
                    "cloudsql" if mon_resource == "cloudsql_database" else "run"
                ):
                    continue
            flt = (
                f'metric.type="{metric}" AND '
                f'resource.type="{mon_resource}"'
            )
            # Scope to the specific resource using the correct label.
            if mon_resource == "gce_instance":
                if provider_id:
                    flt += f' AND resource.labels.instance_id="{provider_id}"'
                else:
                    flt += f' AND resource.labels.instance_name="{name_field}"'
            elif mon_resource == "cloud_run_revision":
                flt += f' AND resource.labels.service_name="{name_field}"'
            elif mon_resource == "cloudsql_database":
                flt += f' AND resource.labels.database_id="{project_id}:{name_field}"'
            interval = monitoring_v3.TimeInterval(
                end_time=now, start_time=start
            )
            req = monitoring_v3.ListTimeSeriesRequest(
                name=f"projects/{project_id}",
                filter=flt,
                interval=interval,
                view=monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
            )
            series = await loop.run_in_executor(None, lambda: list(client.list_time_series(req)))
            values: List[float] = []
            for ts in series:
                for pt in ts.points:
                    v = _extract_value(pt.value)
                    if v is not None:
                        values.append(v)
            if values:
                found_any = True
                if is_float:
                    setattr(rec, field, _avg(values))
                else:
                    setattr(rec, field, sum(values))
    except Exception as exc:  # noqa: BLE001
        logger.debug("metrics for %s failed: %s", rid, exc)
        return None

    if not found_any:
        return None
    return rec


async def collect_metrics(
    resources: List["object"], project_id: str, window_minutes: int = 15
) -> List[MetricRecord]:
    from .base import gather_with_concurrency, ok_results

    tasks = [
        collect_metrics_for_resource(r, project_id, window_minutes=window_minutes)
        for r in resources
    ]
    results = await gather_with_concurrency(10, tasks)
    out = [r for r in ok_results(results) if r is not None]
    logger.info("Collected %d metric samples for %s", len(out), project_id)
    return out
