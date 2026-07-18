"""In-memory sliding-window rate limiting middleware.

Protects the public API from abuse. Limits are applied per client IP using a
fixed-window counter (simple, allocation-free, good enough for a single
Cloud Run instance). For multi-instance deployments a shared store (e.g.
Redis/Memorystore) would be needed, but Cloud Run's default concurrency plus
this per-instance cap already blunts most abuse.

Configuration (env, HAWKEYE_ prefix):
  HAWKEYE_RATE_LIMIT_ENABLED  - "true"/"false" (default true)
  HAWKEYE_RATE_LIMIT_MAX      - requests per window (default 120)
  HAWKEYE_RATE_LIMIT_WINDOW   - window seconds (default 60)
  HAWKEYE_RATE_LIMIT_AUTH_MAX - requests/window for authenticated user endpoints
                                (default 300) — higher because logged-in users
                                legitimately make many calls.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .config import get_settings

# Paths that are cheap health/info probes — never rate limited.
_EXEMPT_PREFIXES = ("/livez",)


class RateLimiter:
    """Fixed-window per-IP counter with separate buckets for auth endpoints."""

    def __init__(self, max_requests: int, window: int, auth_max: int) -> None:
        self.max = max_requests
        self.window = window
        self.auth_max = auth_max
        # ip -> deque of timestamps
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._auth_hits: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, bucket: deque[float], now: float) -> None:
        while bucket and now - bucket[0] >= self.window:
            bucket.popleft()

    def is_allowed(self, ip: str, is_auth: bool) -> tuple[bool, int, int]:
        """Return (allowed, remaining, retry_after_seconds)."""
        now = time.monotonic()
        bucket = self._auth_hits[ip] if is_auth else self._hits[ip]
        limit = self.auth_max if is_auth else self.max
        self._prune(bucket, now)
        if len(bucket) >= limit:
            retry_after = int(self.window - (now - bucket[0])) + 1
            return False, 0, max(retry_after, 1)
        bucket.append(now)
        return True, max(limit - len(bucket), 0), 0


def _client_ip(request: Request) -> str:
    # Respect X-Forwarded-For (Cloud Run sets the real client IP here).
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        settings = get_settings()
        self.enabled = str(settings.rate_limit_enabled).lower() != "false"
        self.limiter = RateLimiter(
            max_requests=settings.rate_limit_max,
            window=settings.rate_limit_window,
            auth_max=settings.rate_limit_auth_max,
        )

    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)

        path = request.url.path
        if any(path.startswith(p) for p in _EXEMPT_PREFIXES):
            return await call_next(request)

        # Authenticated user endpoints get a higher allowance.
        is_auth = path.startswith("/api/user") or path.startswith("/api/me")
        ip = _client_ip(request)
        allowed, remaining, retry_after = self.limiter.is_allowed(ip, is_auth)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Slow down and try again later."},
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self.limiter.auth_max if is_auth else self.limiter.max),
                    "X-RateLimit-Remaining": "0",
                },
            )
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(
            self.limiter.auth_max if is_auth else self.limiter.max
        )
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
