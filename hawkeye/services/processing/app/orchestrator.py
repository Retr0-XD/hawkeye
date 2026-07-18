"""Processing orchestrator (Layer 2 entry point).

Pulls a bounded batch from each subscription, correlates, builds the graph,
detects changes, generates recommendations, persists to Firestore + BigQuery,
then ACKs the messages. Designed to be invoked by a scheduled tick (every 5
minutes) or on-demand via the HTTP endpoint.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List

from .config import Settings, get_settings
from .consumers import (
    ack_all,
    parse_audit,
    parse_billing,
    parse_metrics,
    parse_resources,
    pull_audit,
    pull_billing,
    pull_metrics,
    pull_resources,
)
from .correlate import build_graph, correlate_costs, correlate_metrics, detect_changes_sanitized
from .gcp_clients import get_firestore_client
from .insights import generate_recommendations
from .models import Resource
from .storage import _safe_id, write_bigquery, write_firestore

logger = logging.getLogger("hawkeye.processing.orchestrator")


def _previous_resource_ids(settings: Settings) -> set:
    try:
        db = get_firestore_client()
        docs = db.collection(settings.fs_resources).list_documents()
        # Document ids are sanitized (see storage._safe_id); map back.
        return {_safe_id(d.id) for d in docs}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not load previous resource ids: %s", exc)
        return set()


def process_cycle() -> dict:
    settings = get_settings()
    summary: dict = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "counts": {},
        "errors": [],
    }

    # 1. Pull a bounded batch from each topic (envelopes).
    res_env = pull_resources()
    met_env = pull_metrics()
    bil_env = pull_billing()
    aud_env = pull_audit()
    resources = parse_resources(res_env)
    metrics = parse_metrics(met_env)
    billing = parse_billing(bil_env)
    audit = parse_audit(aud_env)
    summary["counts"] = {
        "resources": len(resources),
        "metrics": len(metrics),
        "billing": len(billing),
        "audit": len(audit),
    }

    if not resources:
        summary["finished_at"] = datetime.now(timezone.utc).isoformat()
        summary["note"] = "no resources in queue; persisting metrics/billing/audit only"
        try:
            write_bigquery(metrics, billing, audit, [], [])
        except Exception as exc:  # noqa: BLE001
            logger.exception("BigQuery write failed")
            summary["errors"].append({"stage": "bigquery", "error": str(exc)})
        if not summary["errors"]:
            ack_all(res_env, met_env, bil_env, aud_env)
            summary["acked"] = True
        return summary

    # 2. Index + correlate.
    res_map: Dict[str, Resource] = {r.id: r for r in resources}
    previous_ids = _previous_resource_ids(settings)
    res_map = correlate_costs(res_map, billing)
    res_map = correlate_metrics(res_map, metrics)
    graph = build_graph(res_map, audit)
    current_sanitized = {_safe_id(rid) for rid in res_map}
    new_ids, deleted_ids, modified_ids = detect_changes_sanitized(
        current_sanitized, previous_ids
    )

    # 3. Insights.
    recommendations = generate_recommendations(res_map)

    # 3b. Alerts for lifecycle changes (Layer 2, op 4).
    from .models import Alert

    alerts = []
    for rid in new_ids:
        alerts.append(
            Alert(
                id=f"{rid}:created",
                name=f"New resource detected: {rid}",
                type="LIFECYCLE_CHANGE",
                resource_id=rid,
                condition="resource appeared in ingestion snapshot",
                severity="LOW",
                details={"change": "created"},
            )
        )
    for rid in deleted_ids:
        alerts.append(
            Alert(
                id=f"{rid}:deleted",
                name=f"Resource removed: {rid}",
                type="LIFECYCLE_CHANGE",
                resource_id=rid,
                condition="resource missing from ingestion snapshot",
                severity="MEDIUM",
                details={"change": "deleted"},
            )
        )

    # 3c. Metric / cost anomaly alerts (Layer 2, op 4 — optional polish).
    # Flags sustained high CPU and billing spikes so the Alerts panel surfaces
    # operational issues, not just inventory changes.
    for res in res_map.values():
        if res.cpu_utilization_avg is not None and res.cpu_utilization_avg >= 85.0:
            alerts.append(
                Alert(
                    id=f"{res.id}:cpu-spike",
                    name=f"High CPU on {res.name}",
                    type="SLO_BREACH",
                    resource_id=res.id,
                    condition=f"cpu_utilization_avg={res.cpu_utilization_avg:.0f}% >= 85%",
                    severity="MEDIUM",
                    details={"metric": "cpu_utilization_avg", "value": res.cpu_utilization_avg},
                )
            )
        if res.cost_trend == "SPIKE" or (
            res.monthly_cost_projection > 0
            and getattr(res, "cost_change_percent", 0) >= 30.0
        ):
            alerts.append(
                Alert(
                    id=f"{res.id}:cost-spike",
                    name=f"Cost spike on {res.name}",
                    type="COST_SPIKE",
                    resource_id=res.id,
                    condition=f"monthly cost trend={res.cost_trend}",
                    severity="MEDIUM",
                    details={"monthly_cost_projection": res.monthly_cost_projection},
                )
            )

    # 4. Persist.
    try:
        write_firestore(res_map, recommendations, graph, new_ids, deleted_ids, alerts)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Firestore write failed")
        summary["errors"].append({"stage": "firestore", "error": str(exc)})
    try:
        write_bigquery(metrics, billing, audit, new_ids, deleted_ids)
    except Exception as exc:  # noqa: BLE001
        logger.exception("BigQuery write failed")
        summary["errors"].append({"stage": "bigquery", "error": str(exc)})

    # 5. ACK only after successful persistence.
    if not summary["errors"]:
        ack_all(res_env, met_env, bil_env, aud_env)
        summary["acked"] = True

    summary["changes"] = {
        "new": new_ids,
        "deleted": deleted_ids,
        "modified": modified_ids,
    }
    summary["recommendations"] = len(recommendations)
    summary["finished_at"] = datetime.now(timezone.utc).isoformat()
    logger.info("Processing cycle complete: %s", summary["counts"])
    return summary
