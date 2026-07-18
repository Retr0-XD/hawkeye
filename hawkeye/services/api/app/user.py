"""User-facing endpoints (Week 7): profile + recommendation approval workflow.

These endpoints require a valid Google ID token (see auth.get_current_user).
The approval workflow lets a user APPROVE/REJECT a recommendation; the decision
is persisted in Firestore and surfaced to the Automation service (Week 8).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from .auth import User, get_current_user
from .config import Settings, get_settings
from .gcp_clients import get_firestore_client

logger = logging.getLogger("hawkeye.api.user")

router = APIRouter(prefix="/api/user", tags=["user"])


def _users_col():
    return get_firestore_client().collection("users")


def _approvals_col():
    return get_firestore_client().collection("recommendation_approvals")


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    """Return the authenticated user's profile (upserted into Firestore)."""
    doc_ref = _users_col().document(user.email)
    doc = doc_ref.get()
    now = datetime.now(timezone.utc).isoformat()
    if not doc.exists:
        doc_ref.set({**user.to_dict(), "created_at": now, "last_login": now})
    else:
        doc_ref.update({"last_login": now, "name": user.name, "picture": user.picture})
    return {**user.to_dict(), "created_at": doc.to_dict().get("created_at", now), "last_login": now}


@router.get("/recommendations")
async def my_recommendations(
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
):
    """List recommendations with the current user's approval state (if any)."""
    from .queries import list_recommendations

    recs = list_recommendations(limit=limit)["items"]
    approvals = {a.id: a.to_dict() for a in _approvals_col().stream()}
    out = []
    for r in recs:
        rid = r.get("id")
        approval = approvals.get(rid, {})
        out.append(
            {
                **r,
                "approval": {
                    "status": approval.get("status"),
                    "by": approval.get("by"),
                    "at": approval.get("at"),
                },
            }
        )
    return {"items": out, "user": user.email}


@router.post("/recommendations/{recommendation_id}/approve")
async def approve_recommendation(
    recommendation_id: str,
    user: User = Depends(get_current_user),
):
    """Approve a recommendation (queues it for the Automation service)."""
    return _record_approval(recommendation_id, "APPROVED", user)


@router.post("/recommendations/{recommendation_id}/reject")
async def reject_recommendation(
    recommendation_id: str,
    user: User = Depends(get_current_user),
):
    """Reject a recommendation."""
    return _record_approval(recommendation_id, "REJECTED", user)


def _record_approval(recommendation_id: str, decision: str, user: User) -> dict:
    settings: Settings = get_settings()
    # Verify the recommendation exists.
    rec_doc = (
        get_firestore_client()
        .collection(settings.fs_recommendations)
        .document(recommendation_id)
        .get()
    )
    if not rec_doc.exists:
        raise HTTPException(status_code=404, detail="recommendation not found")

    now = datetime.now(timezone.utc).isoformat()
    _approvals_col().document(recommendation_id).set(
        {
            "recommendation_id": recommendation_id,
            "status": decision,
            "by": user.email,
            "at": now,
        }
    )
    # Reflect status on the recommendation doc itself for downstream consumers.
    rec_doc.reference.update({"approval_status": decision, "approval_by": user.email, "approval_at": now})
    logger.info("Recommendation %s %s by %s", recommendation_id, decision, user.email)
    return {"recommendation_id": recommendation_id, "status": decision, "by": user.email, "at": now}
