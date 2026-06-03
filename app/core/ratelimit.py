"""Redis-backed rate limiting middleware.

Usage::

    app.add_middleware(RateLimitMiddleware)
"""

import json
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.redis_client import get_redis

# ─── Rate-limit presets ────────────────────────────────────────────────────────
# Maps URL-path prefixes to ``(max_requests, window_seconds)`` tuples.

ENDPOINT_LIMITS: dict[str, tuple[int, int]] = {
    "/api/v1/agents/": (10, 60),  # trigger / agent-status endpoints
}

DEFAULT_LIMIT: tuple[int, int] = (60, 60)  # 60 requests / minute

# Exempt paths (health check, docs)
EXEMPT_PATHS: set[str] = {"/api/v1/health", "/docs", "/openapi.json", "/redoc"}


def _resolve_limit(path: str) -> tuple[int, int]:
    """Return the per-endpoint limit or the default."""
    for prefix, limit in ENDPOINT_LIMITS.items():
        if path.startswith(prefix):
            return limit
    return DEFAULT_LIMIT


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Enforce per-endpoint request-rate limits via Redis sorted sets.

    Each request increments a ``ratelimit:<prefix>:<client_ip>`` sorted set
    key that expires after the window.  When Redis is unreachable requests
    are allowed through (fail-open).
    """

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        path = request.url.path

        # Bypass rate-limiting for exempt paths
        if path in EXEMPT_PATHS:
            return await call_next(request)

        max_reqs, window = _resolve_limit(path)
        client_ip: str = request.client.host if request.client else "unknown"

        prefix: str | None = None
        for p in ENDPOINT_LIMITS:
            if path.startswith(p):
                prefix = p
                break

        redis_key = f"ratelimit:{prefix or 'default'}:{client_ip}"

        try:
            redis = await get_redis()
            now = time.time()
            cutoff = now - window

            # Remove stale entries
            await redis.zremrangebyscore(redis_key, 0, cutoff)  # type: ignore[union-attr]
            count: int = await redis.zcard(redis_key)  # type: ignore[union-attr]

            if count >= max_reqs:
                retry_after = int(window)
                return Response(
                    status_code=429,
                    content=json.dumps(
                        {
                            "detail": "Rate limit exceeded. Please try again later.",
                        }
                    ),
                    media_type="application/json",
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(max_reqs),
                        "X-RateLimit-Remaining": "0",
                    },
                )

            # Record this request
            await redis.zadd(redis_key, {str(now): now})  # type: ignore[union-attr]
            await redis.expire(redis_key, window)  # type: ignore[union-attr]
        except Exception:
            # Fail-open when Redis is unavailable
            pass

        return await call_next(request)
