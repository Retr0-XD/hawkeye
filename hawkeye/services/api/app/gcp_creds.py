"""Per-user service-account credential storage (bring-your-own-cloud).

Users paste their OWN GCP service-account JSON key. We encrypt it with a
server-side Fernet key (HAWKEYE_CREDS_KEY) and store the ciphertext in
Firestore under `user_gcp_credentials/{user_email}`. The plaintext is NEVER
returned to the client and is only used server-side to read the user's own
GCP projects/resources. This avoids Google's restricted OAuth scope, so the
app can stay fully public without verification.

No owner data is ever mixed in — each user's credentials are isolated by their
verified Google email.
"""
from __future__ import annotations

import base64
import json
import logging
import os
from typing import Optional

from cryptography.fernet import Fernet

from .gcp_clients import get_firestore_client

logger = logging.getLogger("hawkeye.api.gcp_creds")

_COLLECTION = "user_gcp_credentials"


def _fernet() -> Fernet:
    key = os.environ.get("HAWKEYE_CREDS_KEY")
    if not key:
        # Dev fallback only; production MUST set HAWKEYE_CREDS_KEY.
        logger.warning("HAWKEYE_CREDS_KEY not set; using ephemeral dev key")
        key = base64.urlsafe_b64encode(b"dev-only-insecure-key-please-set-env-!"[:32].ljust(32, b"0"))
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def _validate_sa(json_str: str) -> dict:
    """Validate that the pasted text is a GCP service-account key."""
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ValueError("Not valid JSON") from exc
    required = ["type", "project_id", "private_key", "client_email"]
    missing = [k for k in required if k not in data]
    if missing:
        raise ValueError(f"Missing fields: {', '.join(missing)}")
    if data.get("type") != "service_account":
        raise ValueError("JSON is not a service_account key")
    return data


def save_credentials(user_email: str, json_str: str) -> dict:
    """Encrypt + store a user's service-account key. Returns metadata only."""
    info = _validate_sa(json_str)
    fernet = _fernet()
    ciphertext = fernet.encrypt(json_str.encode()).decode()
    get_firestore_client().collection(_COLLECTION).document(user_email).set(
        {
            "ciphertext": ciphertext,
            "project_id": info.get("project_id"),
            "client_email": info.get("client_email"),
            "updated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        }
    )
    return {"project_id": info.get("project_id"), "client_email": info.get("client_email")}


def get_credentials_json(user_email: str) -> Optional[str]:
    """Return the decrypted SA JSON for a user, or None if not configured."""
    doc = get_firestore_client().collection(_COLLECTION).document(user_email).get()
    if not doc.exists:
        return None
    data = doc.to_dict() or {}
    ct = data.get("ciphertext")
    if not ct:
        return None
    try:
        return _fernet().decrypt(ct.encode()).decode()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to decrypt credentials for %s: %s", user_email, exc)
        return None


def delete_credentials(user_email: str) -> None:
    get_firestore_client().collection(_COLLECTION).document(user_email).delete()


def has_credentials(user_email: str) -> bool:
    return get_credentials_json(user_email) is not None
