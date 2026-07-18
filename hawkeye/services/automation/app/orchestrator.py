"""Automation orchestrator: scan approved recommendations and execute them."""
from __future__ import annotations

import logging
from typing import Dict, List

from .config import Settings, get_settings
from .executor import execute_approval
from .gcp_clients import get_firestore_client

logger = logging.getLogger("hawkeye.automation.orchestrator")


def run_automation() -> Dict:
    """Find APPROVED recommendations not yet acted on, and execute them."""
    settings = get_settings()
    db = get_firestore_client()

    approvals = list(db.collection(settings.fs_approvals).stream())
    results: List[Dict] = []
    for a in approvals:
        ad = a.to_dict()
        if ad.get("status") != "APPROVED":
            continue
        rec_id = ad.get("recommendation_id")
        rec_doc = db.collection(settings.fs_recommendations).document(rec_id).get()
        if not rec_doc.exists:
            continue
        rec = rec_doc.to_dict()
        rec["id"] = rec_id
        # Skip if already applied by a previous run.
        if rec.get("automation_status") == "APPLIED":
            continue
        try:
            res = execute_approval(rec, ad)
            results.append(res)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to process approval %s", rec_id)
            results.append({"recommendation_id": rec_id, "status": "error", "detail": str(exc)})

    return {"processed": len(results), "results": results, "dry_run": settings.dry_run}
