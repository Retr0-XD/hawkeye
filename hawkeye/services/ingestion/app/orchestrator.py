"""Ingestion orchestrator (Layer 1 entry point).

Implements ``async def ingest_all_projects()`` from the architecture doc:
  1. Resolve the list of projects to ingest (configured project + any cached).
  2. For each project, run the four collectors concurrently.
  3. Publish normalized records to Pub/Sub.
  4. Persist last_sync timestamp in Firestore.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from .collectors.audit_collector import collect_audit
from .collectors.billing_collector import collect_billing
from .collectors.metrics_collector import collect_metrics
from .collectors.resources_collector import collect_resources
from .config import Settings, get_settings
from .gcp_clients import get_firestore_client
from .models import AuditEvent, BillingRecord, MetricRecord, Resource
from .publisher import Publisher

logger = logging.getLogger("hawkeye.ingestion.orchestrator")


def _projects_to_ingest(settings: Settings) -> list[str]:
    # Single-project MVP (GCP-only). Extendable to multi-project later.
    return [settings.gcp_project_id]


async def ingest_all_projects() -> dict:
    """Run a full ingestion cycle. Returns a summary dict."""
    settings = get_settings()
    publisher = Publisher(settings)
    projects = _projects_to_ingest(settings)

    summary = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "projects": {},
        "totals": {"resources": 0, "metrics": 0, "billing": 0, "audit": 0},
        "errors": [],
    }

    for project_id in projects:
        proj_summary: dict = {"resources": 0, "metrics": 0, "billing": 0, "audit": 0}
        try:
            # Step 1-4: collect concurrently per project.
            resources, billing, audit = await asyncio.gather(
                collect_resources(project_id),
                collect_billing(project_id),
                collect_audit(project_id),
            )
            # Metrics depend on resources.
            metrics = await collect_metrics(resources, project_id, window_minutes=15)

            # Step 5: publish to Pub/Sub.
            publisher.publish("resources", [r.to_pubsub() for r in resources])
            publisher.publish("metrics", [m.to_pubsub() for m in metrics])
            publisher.publish("billing", [b.to_pubsub() for b in billing])
            publisher.publish("audit", [a.to_pubsub() for a in audit])

            proj_summary.update(
                resources=len(resources),
                metrics=len(metrics),
                billing=len(billing),
                audit=len(audit),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Ingestion failed for project %s", project_id)
            summary["errors"].append({"project": project_id, "error": str(exc)})

        summary["projects"][project_id] = proj_summary
        for k in ("resources", "metrics", "billing", "audit"):
            summary["totals"][k] += proj_summary[k]

    # Step 6: persist last_sync.
    try:
        db = get_firestore_client()
        doc_ref = db.collection(settings.firestore_state_collection).document(
            settings.firestore_state_doc
        )
        doc_ref.set(
            {
                "last_sync": datetime.now(timezone.utc),
                "totals": summary["totals"],
                "errors": summary["errors"],
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to persist last_sync: %s", exc)
        summary["errors"].append({"stage": "last_sync", "error": str(exc)})

    publisher.flush()
    summary["finished_at"] = datetime.now(timezone.utc).isoformat()
    logger.info("Ingestion cycle complete: %s", summary["totals"])
    return summary
