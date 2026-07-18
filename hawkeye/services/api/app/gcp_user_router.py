"""Per-user GCP router (multi-tenant mode).

Every endpoint reads the logged-in user's OWN GCP data. Two credential models:
1. Google access token (X-Gcp-Token header) — when the user authorized the
   cloud-platform.read-only scope via Google sign-in.
2. Bring-your-own-cloud: the user pastes their own GCP service-account JSON,
   stored encrypted per-user. No restricted OAuth scope / verification needed.

No shared/owner data is ever returned.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query

from .auth import User, get_current_user
from .gcp_creds import (
    delete_credentials,
    get_credentials_json,
    has_credentials,
    save_credentials,
)
from .gcp_user import (
    list_user_projects,
    list_user_resources,
    user_compliance,
)

logger = logging.getLogger("hawkeye.api.gcp_user_router")

router = APIRouter(prefix="/api/user/gcp", tags=["user-gcp"])


def _require_gcp_token(x_gcp_token: str | None = Header(default=None)) -> Optional[str]:
    return x_gcp_token or None


def _resolve_sa(user: User, token: Optional[str]) -> Optional[str]:
    """Prefer a stored service-account key; fall back to the Google token path."""
    sa = get_credentials_json(user.email)
    if sa:
        return sa
    return None  # token path handled by callers when sa is None


@router.get("/status")
async def status(user: User = Depends(get_current_user)):
    """Whether the user has connected their own GCP (service account)."""
    return {"connected": has_credentials(user.email)}


@router.post("/connect")
async def connect(
    user: User = Depends(get_current_user),
    payload: dict = Body(...),
):
    """Store the user's own GCP service-account JSON (encrypted)."""
    sa_json = payload.get("serviceAccountJson")
    if not isinstance(sa_json, str) or not sa_json.strip():
        raise HTTPException(status_code=400, detail="serviceAccountJson is required")
    try:
        meta = save_credentials(user.email, sa_json)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid service account: {exc}")
    return {"connected": True, **meta}


@router.delete("/connect")
async def disconnect(user: User = Depends(get_current_user)):
    delete_credentials(user.email)
    return {"connected": False}


@router.get("/projects")
async def projects(
    user: User = Depends(get_current_user),
    token: Optional[str] = Depends(_require_gcp_token),
):
    sa = _resolve_sa(user, token)
    if sa:
        return {"items": list_user_projects("", sa_json=sa), "user": user.email, "mode": "service-account"}
    if not token:
        raise HTTPException(status_code=400, detail="Connect your GCP account or sign in with GCP access")
    return {"items": list_user_projects(token), "user": user.email, "mode": "google-token"}


@router.get("/resources")
async def resources(
    projectId: str = Query(...),
    user: User = Depends(get_current_user),
    token: Optional[str] = Depends(_require_gcp_token),
):
    sa = _resolve_sa(user, token)
    if sa:
        return {"items": list_user_resources("", projectId, sa_json=sa), "projectId": projectId, "mode": "service-account"}
    if not token:
        raise HTTPException(status_code=400, detail="Connect your GCP account or sign in with GCP access")
    return {"items": list_user_resources(token, projectId), "projectId": projectId, "mode": "google-token"}


@router.get("/compliance")
async def compliance(
    projectId: str = Query(...),
    user: User = Depends(get_current_user),
    token: Optional[str] = Depends(_require_gcp_token),
):
    sa = _resolve_sa(user, token)
    if sa:
        return user_compliance("", projectId, sa_json=sa)
    if not token:
        raise HTTPException(status_code=400, detail="Connect your GCP account or sign in with GCP access")
    return user_compliance(token, projectId)
