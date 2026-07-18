"""Insight & recommendation engine (Layer 2, operation 5).

Generates optimization / security / performance recommendations from the
correlated resource set. Rules-based per the architecture doc (ML layer comes
later). Each recommendation carries an estimated savings and severity.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List

from .config import Settings, get_settings
from .models import Recommendation, Resource

logger = logging.getLogger("hawkeye.processing.insights")


def _age_days(res: Resource) -> float:
    if not res.created_at:
        return 0.0
    created = res.created_at
    if not created.tzinfo:
        created = created.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - created).total_seconds() / 86400.0


def generate_recommendations(resources: Dict[str, Resource]) -> List[Recommendation]:
    settings = get_settings()
    recs: List[Recommendation] = []

    for res in resources.values():
        # Deterministic id per (resource, type) so re-runs overwrite the same
        # Firestore doc instead of accumulating duplicates every cycle.
        def _rec_id(rec_type: str) -> str:
            return f"{res.id}:{rec_type}"
        # --- COST: unused / low-utilization resources -------------------
        cpu = res.cpu_utilization_avg
        mem = res.memory_utilization_avg
        age = _age_days(res)
        monthly = res.monthly_cost_projection or 0.0

        if (
            monthly > 0
            and age >= settings.unused_age_days
            and (cpu is None or cpu < settings.low_cpu_threshold)
            and (mem is None or mem < settings.low_memory_threshold)
        ):
            recs.append(
                Recommendation(
                    id=_rec_id("COST"),
                    type="COST",
                    resource_id=res.id,
                    title=f"Delete unused {res.type} '{res.name}'",
                    description=(
                        f"Resource has been running {age:.0f} days with "
                        f"CPU {cpu}% / memory {mem}% and costs ${monthly:.2f}/mo. "
                        "Likely orphaned."
                    ),
                    estimated_savings=round(monthly * 12, 2),
                    severity="HIGH" if monthly >= 10 else "MEDIUM",
                    confidence=0.8,
                )
            )
        elif (
            monthly > 0
            and (cpu is not None and cpu < settings.low_cpu_threshold)
            and (mem is not None and mem < settings.low_memory_threshold)
        ):
            recs.append(
                Recommendation(
                    id=_rec_id("COST"),
                    type="COST",
                    resource_id=res.id,
                    title=f"Downsize over-provisioned {res.type} '{res.name}'",
                    description=(
                        f"Avg CPU {cpu}% / memory {mem}% while costing "
                        f"${monthly:.2f}/mo. Consider a smaller machine type."
                    ),
                    estimated_savings=round(monthly * 12 * 0.5, 2),
                    severity="MEDIUM",
                    confidence=0.6,
                )
            )

        # --- SECURITY: public access / unencrypted ----------------------
        if res.public_access and res.type in ("Database", "Storage"):
            recs.append(
                Recommendation(
                    id=_rec_id("SECURITY"),
                    type="SECURITY",
                    resource_id=res.id,
                    title=f"Restrict public access on {res.type} '{res.name}'",
                    description=(
                        "Resource is publicly accessible. Restrict via IAM / "
                        "VPC Service Controls unless intentionally public."
                    ),
                    estimated_savings=0.0,
                    severity="HIGH",
                    confidence=0.9,
                )
            )
        if res.encryption_status == "UNENCRYPTED":
            recs.append(
                Recommendation(
                    id=_rec_id("SECURITY"),
                    type="SECURITY",
                    resource_id=res.id,
                    title=f"Enable encryption on {res.type} '{res.name}'",
                    description="Resource reports unencrypted data at rest.",
                    estimated_savings=0.0,
                    severity="MEDIUM",
                    confidence=0.9,
                )
            )

        # --- RELIABILITY: missing backups / audit logging ---------------
        if res.backup_enabled is False and res.type in ("Database", "Storage"):
            recs.append(
                Recommendation(
                    id=_rec_id("RELIABILITY"),
                    type="RELIABILITY",
                    resource_id=res.id,
                    title=f"Enable backups on {res.type} '{res.name}'",
                    description=(
                        "No backup policy is configured. Enable automated "
                        "snapshots to protect against data loss."
                    ),
                    estimated_savings=0.0,
                    severity="MEDIUM",
                    confidence=0.85,
                )
            )
        if res.audit_logging_enabled is False:
            recs.append(
                Recommendation(
                    id=_rec_id("GOVERNANCE"),
                    type="GOVERNANCE",
                    resource_id=res.id,
                    title=f"Enable audit logging on '{res.name}'",
                    description=(
                        "Audit logging is disabled — configuration and access "
                        "changes are not traceable for compliance."
                    ),
                    estimated_savings=0.0,
                    severity="LOW",
                    confidence=0.8,
                )
            )

        # --- PERFORMANCE: high error rate / instability ------------------
        err = res.error_rate_avg if hasattr(res, "error_rate_avg") else None
        if err is not None and err > 2.0:
            recs.append(
                Recommendation(
                    id=_rec_id("PERFORMANCE"),
                    type="PERFORMANCE",
                    resource_id=res.id,
                    title=f"Investigate elevated error rate on '{res.name}'",
                    description=(
                        f"Average error rate is {err:.1f}%, above the 2% SLO "
                        "threshold. Check dependencies and recent deploys."
                    ),
                    estimated_savings=0.0,
                    severity="MEDIUM",
                    confidence=0.7,
                )
            )

        # --- GOVERNANCE: missing owner / labels --------------------------
        if not res.owner_email and not res.labels:
            recs.append(
                Recommendation(
                    id=_rec_id("GOVERNANCE"),
                    type="GOVERNANCE",
                    resource_id=res.id,
                    title=f"Tag ownership for '{res.name}'",
                    description=(
                        "Resource has no owner email and no labels — hard to "
                        "attribute cost or route incidents."
                    ),
                    estimated_savings=0.0,
                    severity="LOW",
                    confidence=0.6,
                )
            )

    # Attach recommendation ids back onto the resource for quick lookup.
    for rec in recs:
        if rec.resource_id in resources:
            resources[rec.resource_id].pending_recommendations.append(rec.id)
            resources[rec.resource_id].optimization_potential_dollars += rec.estimated_savings

    logger.info("Generated %d recommendations", len(recs))
    return recs
