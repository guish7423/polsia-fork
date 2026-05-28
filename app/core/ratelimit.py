"""Simple in-memory rate limiter — token bucket per IP."""

import time
from collections import defaultdict

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from app.config import settings


class TokenBucket:
    """Token bucket rate limiter — per-IP, per-minute."""

    def __init__(self, rate: int = 60):
        self.rate = rate
        self._buckets: dict[str, dict] = defaultdict(
            lambda: {"tokens": rate, "last_refill": time.monotonic()}
        )

    def _refill(self, ip: str):
        bucket = self._buckets[ip]
        now = time.monotonic()
        elapsed = now - bucket["last_refill"]
        tokens_to_add = int(elapsed * (self.rate / 60.0))
        if tokens_to_add > 0:
            bucket["tokens"] = min(self.rate, bucket["tokens"] + tokens_to_add)
            bucket["last_refill"] = now

    def consume(self, ip: str) -> bool:
        """Try to consume one token. Returns True if allowed."""
        self._refill(ip)
        bucket = self._buckets[ip]
        if bucket["tokens"] > 0:
            bucket["tokens"] -= 1
            return True
        return False

    def remaining(self, ip: str) -> int:
        self._refill(ip)
        return self._buckets[ip]["tokens"]


# Global rate limiter instance
_rate_limiter = TokenBucket(rate=settings.rate_limit_per_minute)


async def rate_limit_middleware(request: Request, call_next):
    """FastAPI middleware that rate-limits API requests per IP."""
    # Skip rate limiting for health checks and WebSocket
    if request.url.path in ("/api/v1/health",) or request.url.path.startswith("/ws"):
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    if not _rate_limiter.consume(client_ip):
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Rate limit exceeded. Try again later.",
                "retry_after_seconds": 60,
            },
            headers={"Retry-After": "60"},
        )

    response = await call_next(request)
    response.headers["X-RateLimit-Remaining"] = str(_rate_limiter.remaining(client_ip))
    return response
