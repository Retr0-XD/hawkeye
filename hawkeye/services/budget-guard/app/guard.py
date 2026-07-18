"""Suspend / resume logic for the free-forever safety net.

When over the monthly cap:
  - Revoke public (unauthenticated) access on all Cloud Run services
    so they cannot be invoked (they still scale to 0, but no traffic
    can trigger billable invocations).
  - Pause any Cloud Scheduler jobs (so the ingestion cron stops).
When the new month starts:
  - Restore public access + resume schedulers.

State is persisted in Firestore so the guard is idempotent across
restarts and knows whether it already suspended this month.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, UTC
from typing import List

from google.cloud import firestore
from google.cloud import run_v2
from google.cloud import scheduler_v1

from .config import Settings, get_settings

logger = logging.getLogger("hawkeye.budget-guard.guard")

# Services that should be guarded (all billable Cloud Run services).
# Kept in sync with the deployed services in dice-master-the-platform.
GUARDED_SERVICES = [
    "aether", "apollo", "athena", "atlas", "cost-guard",
    "dashboard", "lattice", "odin", "orion",
    "hawkeye-ingestion", "hawkeye-processing", "hawkeye-api", "budget-guard",
]


def _month_key() -> str:
    return datetime.now(UTC).strftime("%Y-%m")


def _state_doc(settings: Settings):
    db = firestore.Client(project=settings.gcp_project_id)
    return db.collection(settings.state_collection).document(settings.state_doc)


def get_state(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    doc = _state_doc(settings).get()
    return doc.to_dict() if doc.exists else {}


def set_state(suspended: bool, cost: float, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    _state_doc(settings).set(
        {
            "suspended": suspended,
            "suspended_month": _month_key() if suspended else None,
            "last_cost_usd": cost,
            "updated_at": datetime.now(timezone.utc),
        }
    )


def suspend_all(settings: Settings | None = None) -> List[str]:
    """Revoke public access on guarded services + pause schedulers."""
    settings = settings or get_settings()
    actions: List[str] = []

    # 1. Revoke unauthenticated access on Cloud Run services.
    run_client = run_v2.ServicesClient()
    policy = {"allUsers": "roles/run.invoker"}
    for svc in GUARDED_SERVICES:
        try:
            name = f"projects/{settings.gcp_project_id}/locations/{settings.region}/services/{svc}"
            run_client.remove_iam_policy_binding(resource=name, binding=policy)
            actions.append(f"revoked-public:{svc}")
        except Exception as exc:  # noqa: BLE001
            logger.warning("revoke failed for %s: %s", svc, exc)

    # 2. Pause Cloud Scheduler jobs (all jobs in the region unless a
    #    specific allow-list is configured).
    sched_client = scheduler_v1.CloudSchedulerClient()
    parent = f"projects/{settings.gcp_project_id}/locations/{settings.region}"
    jobs = settings.scheduler_jobs or [
        j.name.split("/")[-1] for j in sched_client.list_jobs(parent=parent)
    ]
    for job in jobs:
        try:
            sched_client.pause_job(name=f"{parent}/jobs/{job}")
            actions.append(f"paused:{job}")
        except Exception as exc:  # noqa: BLE001
            logger.warning("pause failed for %s: %s", job, exc)

    logger.warning("SUSPENDED all services. Actions: %s", actions)
    return actions


def resume_all(settings: Settings | None = None) -> List[str]:
    """Restore public access on guarded services + resume schedulers."""
    settings = settings or get_settings()
    actions: List[str] = []

    run_client = run_v2.ServicesClient()
    policy = {"allUsers": "roles/run.invoker"}
    for svc in GUARDED_SERVICES:
        try:
            name = f"projects/{settings.gcp_project_id}/locations/{settings.region}/services/{svc}"
            run_client.add_iam_policy_binding(resource=name, binding=policy)
            actions.append(f"restored-public:{svc}")
        except Exception as exc:  # noqa: BLE001
            logger.warning("restore failed for %s: %s", svc, exc)

    sched_client = scheduler_v1.CloudSchedulerClient()
    parent = f"projects/{settings.gcp_project_id}/locations/{settings.region}"
    jobs = settings.scheduler_jobs or [
        j.name.split("/")[-1] for j in sched_client.list_jobs(parent=parent)
    ]
    for job in jobs:
        try:
            sched_client.resume_job(name=f"{parent}/jobs/{job}")
            actions.append(f"resumed:{job}")
        except Exception as exc:  # noqa: BLE001
            logger.warning("resume failed for %s: %s", job, exc)

    logger.info("RESUMED all services. Actions: %s", actions)
    return actions
