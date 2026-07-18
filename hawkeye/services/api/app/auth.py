"""Authentication for the Hawkeye User API (Week 7).

Uses Google Identity Services: the frontend obtains a Google ID token (JWT)
and sends it as `Authorization: Bearer <id_token>`. We verify the token's
signature + audience + expiry with google-auth and extract the user's email.

The demo dashboard (Week 6) remains public and unauthenticated. The user
endpoints under /api/user/* require a valid token.

To allow a user: set HAWKEYE_ALLOWED_EMAILS (comma-separated) or leave empty to
allow any Google-authenticated account in the project's domain. For MVP we
allow any verified Google account and record the email in Firestore `users`.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from .config import Settings, get_settings

logger = logging.getLogger("hawkeye.api.auth")

_bearer = HTTPBearer(auto_error=False)


class User:
    def __init__(self, email: str, name: str = "", picture: str = "", sub: str = ""):
        self.email = email
        self.name = name
        self.picture = picture
        self.sub = sub

    def to_dict(self) -> dict:
        return {"email": self.email, "name": self.name, "picture": self.picture, "sub": self.sub}


@lru_cache
def _allowed_emails(raw: str) -> set:
    if not raw:
        return set()
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def verify_id_token(token: str, settings: Settings) -> User:
    """Verify a Google ID token and return the authenticated User.

    Fails closed: the OAuth client id MUST be configured, otherwise the
    audience is not verified and any Google-issued token would be accepted.
    """
    if not settings.oauth_client_id:
        logger.error("oauth_client_id is not configured; refusing to verify tokens")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Auth not configured",
        )
    try:
        payload = google_id_token.verify_token(
            token,
            request=google_requests.Request(),
            audience=settings.oauth_client_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("ID token verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired ID token",
        )

    email = payload.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ID token missing email",
        )
    # Optional allow-list.
    allowed = _allowed_emails(settings.allowed_emails or "")
    if allowed and email.lower() not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account not authorized",
        )
    return User(
        email=email,
        name=payload.get("name", ""),
        picture=payload.get("picture", ""),
        sub=payload.get("sub", ""),
    )


async def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> User:
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_id_token(creds.credentials, get_settings())
