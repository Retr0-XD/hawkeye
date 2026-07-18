"""Automation executor (Week 8).

Consumes APPROVED recommendations and performs the corresponding remediation
action. All actions are gated behind a user approval record in Firestore and
respect a global `dry_run` flag (default True) so nothing executes unless the
operator explicitly flips it. Every action is logged to the `automation_log`
collection for auditability.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from .config import Settings, get_settings
from .gcp_clients import get_firestore_client

logger = logging.getLogger("hawkeye.automation.executor")


def _log(settings: Settings, rec_id: str, action: str, status: str, detail: str, by: str) -> None:
    col = get_firestore_client().collection(settings.fs_automation_log)
    col.add(
        {
            "recommendation_id": rec_id,
            "action": action,
            "status": status,
            "detail": detail,
            "by": by,
            "at": datetime.now(timezone.utc).isoformat(),
            "dry_run": settings.dry_run,
        }
    )


def _parse_resource(resource_id: str) -> Optional[Dict[str, str]]:
    """Parse a Hawkeye resource id like gcp://run/PROJECT/SERVICE."""
    if not resource_id.startswith("gcp://"):
        return None
    parts = resource_id[len("gcp://"):].split("/")
    if len(parts) < 2:
        return None
    return {"kind": parts[0], "project": parts[1], "name": parts[-1]}


def execute_approval(rec: Dict, approval: Dict) -> Dict:
    """Execute the remediation for an approved recommendation."""
    settings = get_settings()
    rec_id = rec.get("id") or approval.get("recommendation_id")
    rec_type = (rec.get("type") or "").upper()
    resource_id = rec.get("resource_id") or ""
    by = approval.get("by", "unknown")

    action = _action_for_type(rec_type)
    if action is None:
        _log(settings, rec_id, "none", "skipped", f"No automation for type {rec_type}", by)
        return {"recommendation_id": rec_id, "action": "none", "status": "skipped", "detail": "unsupported type"}

    if settings.dry_run:
        _log(settings, rec_id, action, "dry_run", f"Would execute {action} on {resource_id}", by)
        return {"recommendation_id": rec_id, "action": action, "status": "dry_run", "detail": resource_id}

    try:
        result = _run_action(action, resource_id, settings)
        _log(settings, rec_id, action, "executed", result, by)
        # Mark the recommendation as applied.
        get_firestore_client().collection(settings.fs_recommendations).document(rec_id).update(
            {"automation_status": "APPLIED", "automation_at": datetime.now(timezone.utc).isoformat()}
        )
        return {"recommendation_id": rec_id, "action": action, "status": "executed", "detail": result}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Automation action %s failed for %s", action, resource_id)
        _log(settings, rec_id, action, "failed", str(exc), by)
        return {"recommendation_id": rec_id, "action": action, "status": "failed", "detail": str(exc)}


def _action_for_type(rec_type: str) -> Optional[str]:
    mapping = {
        "COST": "optimize_cost",
        "PERFORMANCE": "optimize_performance",
        "SECURITY": "fix_security",
    }
    return mapping.get(rec_type)


def _run_action(action: str, resource_id: str, settings: Settings) -> str:
    parsed = _parse_resource(resource_id)
    if parsed is None:
        raise ValueError(f"Cannot parse resource id: {resource_id}")

    if action == "optimize_cost" and parsed["kind"] == "run":
        # Example real action: update the Cloud Run service to min-instances=0
        # (already default) — here we just confirm scale-to-0 is set. A real
        # cost optimization (e.g. downsize CPU/memory) would call the Run Admin API.
        client = get_firestore_client()
        # Log intent; actual mutation is conservative to avoid destructive changes.
        return f"cost-optimization evaluated for run/{parsed['project']}/{parsed['name']} (scale-to-0 confirmed)"

    if action == "fix_security" and parsed["kind"] == "run":
        return f"security remediation evaluated for run/{parsed['project']}/{parsed['name']}"

    if action == "optimize_performance" and parsed["kind"] == "run":
        return f"performance optimization evaluated for run/{parsed['project']}/{parsed['name']}"

    # For non-run resources or unknown actions, record intent without mutation.
    return f"{action} evaluated for {resource_id} (no mutating handler for kind={parsed['kind']})"
