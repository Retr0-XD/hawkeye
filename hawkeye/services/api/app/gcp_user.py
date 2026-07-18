"""Per-user GCP reads (multi-tenant mode).

Two credential models are supported, both scoped to the logged-in user so they
only ever see THEIR OWN GCP data (never the owner's shared dataset):

1. Google access token (X-Gcp-Token header) — used when the user authorized the
   `cloud-platform.read-only` scope via Google sign-in. REST calls to Google.
2. Service-account JSON (bring-your-own-cloud) — the user pastes their own GCP
   service-account key; we build a google-auth Credentials object and call the
   Google client libraries. No Google verification / restricted scope needed.

This lets the app stay fully public (basic Google sign-in only, no verification)
while still reading each user's own cloud via credentials THEY provide.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import google.auth
import google.auth.transport.requests
import requests
from google.oauth2 import service_account

logger = logging.getLogger("hawkeye.api.gcp_user")

_CLOUD_ASSET = "https://cloudasset.googleapis.com/v1"
_RESOURCE_MANAGER = "https://cloudresourcemanager.googleapis.com/v1"
# Read-only, no write scopes. This is the minimum needed to list a user's
# projects, resources, IAM policy and org policy.
GCP_READ_SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform.read-only",
    "openid",
    "email",
    "profile",
]


def _sa_credentials(sa_json: str) -> service_account.Credentials:
    """Build service-account Credentials from a pasted JSON key."""
    creds = service_account.Credentials.from_service_account_info(
        __import__("json").loads(sa_json),
        scopes=["https://www.googleapis.com/auth/cloud-platform.read-only"],
    )
    return creds


def _sa_session(sa_json: str) -> requests.Session:
    """Return an authorized requests.Session using the SA credentials."""
    creds = _sa_credentials(sa_json)
    sess = requests.Session()
    creds.refresh(google.auth.transport.requests.Request())
    sess.headers.update({"Authorization": f"Bearer {creds.token}"})
    return sess


def _headers(access_token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }


def list_user_projects(access_token: str, sa_json: Optional[str] = None) -> List[Dict]:
    """Return the projects the user can view (via Resource Manager)."""
    sess: Optional[requests.Session] = _sa_session(sa_json) if sa_json else None
    out: List[Dict] = []
    page_token: Optional[str] = None
    # Resource Manager v1 list uses `pageToken`/`pageSize`; v3 uses `pageSize`.
    for _ in range(10):  # cap pagination
        params = {"pageSize": 50}
        if page_token:
            params["pageToken"] = page_token
        r = (sess or requests).get(
            f"{_RESOURCE_MANAGER}/projects",
            headers=_headers(access_token) if not sess else None,
            params=params,
            timeout=15,
        ) if not sess else sess.get(
            f"{_RESOURCE_MANAGER}/projects",
            params=params,
            timeout=15,
        )
        if r.status_code != 200:
            logger.warning("list_user_projects failed: %s %s", r.status_code, r.text[:200])
            break
        body = r.json()
        for p in body.get("projects", []):
            out.append(
                {
                    "projectId": p.get("projectId"),
                    "name": p.get("name"),
                    "projectNumber": p.get("projectNumber"),
                    "state": p.get("lifecycleState"),
                }
            )
        page_token = body.get("nextPageToken")
        if not page_token:
            break
    return out


def list_user_resources(access_token: str, project_id: str, sa_json: Optional[str] = None) -> List[Dict]:
    """List assets in a project via Cloud Asset Inventory (searchAllResources).

    Returns a normalized list of resources with id/name/type/region/project.
    """
    out: List[Dict] = []
    page_token: Optional[str] = None
    for _ in range(10):
        params = {
            "scope": f"projects/{project_id}",
            "pageSize": 100,
            "assetTypes": ",".join(
                [
                    "compute.googleapis.com/Instance",
                    "compute.googleapis.com/InstanceGroup",
                    "container.googleapis.com/Cluster",
                    "run.googleapis.com/Service",
                    "cloudfunctions.googleapis.com/CloudFunction",
                    "storage.googleapis.com/Bucket",
                    "sqladmin.googleapis.com/Instance",
                    "bigquery.googleapis.com/Dataset",
                    "pubsub.googleapis.com/Topic",
                    "artifactregistry.googleapis.com/Repository",
                ]
            ),
        }
        if page_token:
            params["pageToken"] = page_token
        sess = _sa_session(sa_json) if sa_json else None
        r = (sess or requests).get(
            f"{_CLOUD_ASSET}/resources:searchAllResources",
            headers=_headers(access_token) if not sess else None,
            params=params,
            timeout=20,
        ) if not sess else sess.get(
            f"{_CLOUD_ASSET}/resources:searchAllResources",
            params=params,
            timeout=20,
        )
        if r.status_code != 200:
            logger.warning("list_user_resources failed: %s %s", r.status_code, r.text[:200])
            break
        body = r.json()
        for a in body.get("results", []):
            out.append(
                {
                    "id": f"gcp://{_kind_short(a.get('assetType',''))}/{project_id}/{a.get('name','').split('/')[-1]}",
                    "name": a.get("displayName") or a.get("name", "").split("/")[-1],
                    "type": _map_type(a.get("assetType", "")),
                    "project_id": project_id,
                    "region": (a.get("location") or "").split("/")[-1] or None,
                    "status": "ACTIVE",
                    "assetType": a.get("assetType"),
                }
            )
        page_token = body.get("nextPageToken")
        if not page_token:
            break
    return out


def _kind_short(asset_type: str) -> str:
    # "compute.googleapis.com/Instance" -> "compute"
    return asset_type.split(".")[0] if asset_type else "unknown"


def _map_type(asset_type: str) -> str:
    t = asset_type.lower()
    if "run.googleapis.com" in t:
        return "Container"
    if "cloudfunctions" in t:
        return "Function"
    if "sqladmin" in t or "bigquery" in t:
        return "Database"
    if "storage.googleapis.com" in t:
        return "Storage"
    if "compute" in t:
        return "Compute"
    if "container.googleapis.com" in t:
        return "Container-cluster"
    if "pubsub" in t:
        return "Network"
    return "Other"


def user_compliance(access_token: str, project_id: str, sa_json: Optional[str] = None) -> Dict:
    """Lightweight compliance signals from IAM policy (public/wide access)."""
    sess = _sa_session(sa_json) if sa_json else None
    # Count members on the project IAM policy; flag allUsers/allAuthenticatedUsers.
    r = (sess or requests).get(
        f"{_RESOURCE_MANAGER}/projects/{project_id}/getIamPolicy",
        headers=_headers(access_token) if not sess else None,
        params={"options.requestedPolicyVersion": "3"},
        timeout=15,
    ) if not sess else sess.get(
        f"{_RESOURCE_MANAGER}/projects/{project_id}/getIamPolicy",
        params={"options.requestedPolicyVersion": "3"},
        timeout=15,
    )
    public_resources: List[str] = []
    if r.status_code == 200:
        bindings = r.json().get("bindings", [])
        for b in bindings:
            members = b.get("members", [])
            if any(m in ("allUsers", "allAuthenticatedUsers") for m in members):
                public_resources.append(b.get("role", "unknown"))
    return {
        "project_id": project_id,
        "score": 100 if not public_resources else max(0, 100 - 20 * len(public_resources)),
        "violations": len(public_resources),
        "public_iam_roles": public_resources,
    }
