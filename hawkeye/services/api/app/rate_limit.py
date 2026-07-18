"""Global, shared-store rate limiting middleware.

Protects the public API from abuse. Unlike a per-instance in-memory counter,
this limiter stores hit counts in **Firestore** so the cap is enforced
*across all Cloud Run instances* — a hard global limit regardless of how many
replicas are running. No new infrastructure is required (Firestore is already
used by the API).

Design:
  - One document per (bucket, client-ip) under the `rate_limits` collection,
    holding {start: epoch_seconds, count: int, updated: epoch_seconds}.
  - Each request runs inside a Firestore **transaction** that atomically
    reads, decides, and increments — so concurrent requests from the same IP
    across different instances can't both slip past the limit.
  - Old documents auto-expire via a Firestore TTL policy on the `updated`
    field (enabled out-of-band; see deploy notes).

Configuration (env, HAWKEYE_ prefix):
  HAWKEYE_RATE_LIMIT_ENABLED  - "true"/"false" (default true)
  HAWKEYE_RATE_LIMIT_MAX      - requests per window (default 120)
  HAWKEYE_RATE_LIMIT_WINDOW   - window seconds (default 60)
  HAWKEYE_RATE_LIMIT_AUTH_MAX - requests/window for authenticated user endpoints
                                (default 300) — higher because logged-in users
                                legitimately make many calls.
"""
from __future__ import annotations

import logging
import time

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .config import get_settings

logger = logging.getLogger("hawkeye.api.rate_limit")

# Paths that are cheap health/info probes — never rate limited.
_EXEMPT_PREFIXES = ("/livez",)
_COLLECTION = "rate_limits"


class _MemoryStore:
    """In-memory fallback used only if Firestore is unavailable."""

    def __init__(self, window: int) -> None:
        self.window = window
        self._data: dict[str, tuple[float, int]] = {}

    def check_and_increment(self, key: str, limit: int):
        now = time.time()
        start, count = self._data.get(key, (now, 0))
        if now - start >= self.window:
            start, count = now, 0
        if count >= limit:
            retry = int(self.window - (now - start)) + 1
            return False, 0, max(retry, 1)
        count += 1
        self._data[key] = (start, count)
        return True, max(limit - count, 0), 0


class _FirestoreStore:
    """Global, transactional rate-limit store backed by Firestore."""

    def __init__(self, db, window: int) -> None:
        from google.cloud import firestore

        self.db = db
        self.window = window
        self._col = db.collection(_COLLECTION)
        self._firestore = firestore

    def check_and_increment(self, key: str, limit: int):
        from google.cloud import firestore

        now = time.time()

        @firestore.transactional
        def _apply(transaction):
            ref = self._col.document(key)
            snap = ref.get(transaction=transaction)
            data = snap.to_dict() or {}
            start = data.get("start", now)
            count = data.get("count", 0)
            if now - start >= self.window:
                start, count = now, 0
            if count >= limit:
                retry = int(self.window - (now - start)) + 1
                return False, 0, max(retry, 1)
            count += 1
            transaction.set(ref, {"start": start, "count": count, "updated": now})
            return True, max(limit - count, 0), 0

        # A Firestore transaction can only be run once, so build a fresh one
        # per request.
        return _apply(self.db.transaction())


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        settings = get_settings()
        self.enabled = str(settings.rate_limit_enabled).lower() != "false"
        self.window = settings.rate_limit_window
        self.max = settings.rate_limit_max
        self.auth_max = settings.rate_limit_auth_max
        self._store = self._build_store(settings)

    @staticmethod
    def _build_store(settings) -> object:
        try:
            from .gcp_clients import get_firestore_client

            db = get_firestore_client()
            logger.info("Rate limiter using shared Firestore store (global cap)")
            return _FirestoreStore(db, settings.rate_limit_window)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Firestore unavailable for rate limiter (%s); using in-memory "
                "per-instance store (cap scales with instance count)",
                exc,
            )
            return _MemoryStore(settings.rate_limit_window)

    def _client_ip(self, request: Request) -> str:
        # Respect X-Forwarded-For (Cloud Run sets the real client IP here).
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)

        path = request.url.path
        if any(path.startswith(p) for p in _EXEMPT_PREFIXES):
            return await call_next(request)

        # Authenticated user endpoints get a higher allowance.
        is_auth = path.startswith("/api/user") or path.startswith("/api/me")
        ip = self._client_ip(request)
        bucket = "auth" if is_auth else "pub"
        limit = self.auth_max if is_auth else self.max
        key = f"{bucket}:{ip}"

        try:
            allowed, remaining, retry_after = self._store.check_and_increment(key, limit)
        except Exception as exc:  # noqa: BLE001
            # Fail open: never block traffic because the limiter itself errored.
            logger.warning("Rate limiter error (%s); allowing request", exc)
            return await call_next(request)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Slow down and try again later."},
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                },
            )
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
