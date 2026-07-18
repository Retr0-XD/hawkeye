"""Correlation engine (Layer 2, operations 1-4).

Pure functions that take the pulled records and produce:
  - enriched Resource docs (cost + metric rollups attached)
  - a dependency graph (edges between resources)
  - a set of lifecycle change events (new / deleted / modified)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Tuple

from .config import Settings, get_settings
from .models import AuditEvent, BillingRecord, MetricRecord, Resource

logger = logging.getLogger("hawkeye.processing.correlate")


def correlate_costs(
    resources: Dict[str, Resource], billing: List[BillingRecord]
) -> Dict[str, Resource]:
    """Attach monthly cost projection + trend to each resource."""
    by_resource: Dict[str, List[BillingRecord]] = {}
    for b in billing:
        by_resource.setdefault(b.resource_id, []).append(b)

    for rid, recs in by_resource.items():
        if rid not in resources:
            continue
        recs.sort(key=lambda r: r.date)
        latest = recs[-1]
        res = resources[rid]
        res.monthly_cost_projection = round(latest.month_to_date, 4)
        res.cost_trend = (
            "UP" if latest.cost_change_percent > 5
            else "DOWN" if latest.cost_change_percent < -5
            else "STABLE"
        )
        res.last_cost_update = datetime.now(timezone.utc)
    return resources


def correlate_metrics(
    resources: Dict[str, Resource], metrics: List[MetricRecord]
) -> Dict[str, Resource]:
    """Roll up the latest metric sample onto each resource."""
    by_resource: Dict[str, List[MetricRecord]] = {}
    for m in metrics:
        by_resource.setdefault(m.resource_id, []).append(m)

    for rid, recs in by_resource.items():
        if rid not in resources:
            continue
        recs.sort(key=lambda r: r.timestamp if isinstance(r.timestamp, datetime) else datetime.min.replace(tzinfo=timezone.utc))
        latest = recs[-1]
        res = resources[rid]
        res.cpu_utilization_avg = latest.cpu_percent_avg if latest.cpu_percent_avg is not None else latest.cpu_percent
        res.memory_utilization_avg = latest.memory_percent
        if latest.network_out_bytes is not None:
            res.network_egress_gb = round(latest.network_out_bytes / (1024 ** 3), 6)
        res.last_metric_update = datetime.now(timezone.utc)
    return resources


def build_graph(
    resources: Dict[str, Resource], audit: List[AuditEvent]
) -> Dict[str, List[str]]:
    """Build a dependency graph.

    Explicit edges come from ``parent_resources`` / ``child_resources`` on each
    resource. Implicit edges are inferred from audit events that reference two
    resources (e.g. a CREATE of a backend VM by a load-balancer action).
    """
    graph: Dict[str, List[str]] = {rid: [] for rid in resources}

    for res in resources.values():
        for parent in res.parent_resources:
            if parent in graph and parent != res.id:
                graph[parent].append(res.id)
        for child in res.child_resources:
            if child in graph and child != res.id:
                graph[res.id].append(child)

    # Implicit edges from audit: link the actor resource to the target.
    for ev in audit:
        if ev.resource_id and ev.resource_id in graph:
            for other in (ev.changes or {}).get("related_resources", []):
                if other in graph and other != ev.resource_id:
                    if other not in graph[ev.resource_id]:
                        graph[ev.resource_id].append(other)
    return graph


def detect_changes_sanitized(
    current_ids: set, previous_ids: set
) -> Tuple[List[str], List[str], List[str]]:
    """Compare the current batch's (sanitized) ids to Firestore's known set.

    A resource is "new" if it is in the current batch but was not previously
    seen in Firestore. We deliberately do NOT flag "deleted" here: a processing
    run only consumes a partial Pub/Sub batch, so resources written in a prior
    batch would falsely appear missing. True deletions are detected by a
    separate full-snapshot reconciliation (see orchestrator note), not per
    partial batch.

    Returns (new_ids, deleted_ids, modified_ids).
    """
    new_ids = sorted(current_ids - previous_ids)
    deleted_ids: List[str] = []
    modified_ids: List[str] = []
    return new_ids, deleted_ids, modified_ids
