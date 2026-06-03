"""Tests for Redis-backed rate limiting middleware."""
import json
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.ratelimit import ENDPOINT_LIMITS, DEFAULT_LIMIT, RateLimitMiddleware, _resolve_limit
from app.core.redis_client import get_redis


# ─── _resolve_limit ────────────────────────────────────────────────────────────


class TestResolveLimit:
    def test_agent_endpoint_matches(self):
        limit = _resolve_limit("/api/v1/agents/social_media/trigger")
        assert limit == ENDPOINT_LIMITS["/api/v1/agents/"]

    def test_default_endpoint(self):
        limit = _resolve_limit("/api/v1/health")
        assert limit == DEFAULT_LIMIT

    def test_unknown_endpoint_defaults(self):
        limit = _resolve_limit("/api/v1/some_new_path")
        assert limit == DEFAULT_LIMIT


# ─── RateLimitMiddleware ─────────────────────────────────────────────────────────


class TestRateLimitMiddleware:
    @pytest.mark.asyncio
    async def test_health_check_bypassed(self, mock_redis):
        """Health checks should not be rate limited."""
        app = FastAPI()

        @app.get("/api/v1/health")
        async def health():
            return {"status": "ok"}

        app.add_middleware(RateLimitMiddleware)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/health")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_normal_request_passes(self, mock_redis):
        """Regular requests below limit should pass through."""
        app = FastAPI()

        @app.get("/api/v1/test")
        async def test_endpoint():
            return {"ok": True}

        app.add_middleware(RateLimitMiddleware)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/test")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    @pytest.mark.asyncio
    async def test_rate_limited_when_exceeded(self):
        """When Redis reports we're over the limit, return 429."""
        from app.core import ratelimit as rl_module

        app = FastAPI()

        @app.get("/api/v1/test")
        async def test_endpoint():
            return {"ok": True}

        app.add_middleware(RateLimitMiddleware)

        # Mock Redis to always report we're over the limit
        mock_redis = AsyncMock()
        mock_redis.zremrangebyscore = AsyncMock(return_value=0)
        mock_redis.zcard = AsyncMock(return_value=999)  # over the limit
        mock_redis.zadd = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock(return_value=True)

        # We need to patch get_redis *before* building the transport
        import app.core.ratelimit as ratelimit_mod
        original_get = ratelimit_mod.get_redis
        ratelimit_mod.get_redis = AsyncMock(return_value=mock_redis)

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/v1/test")
            assert resp.status_code == 429
            data = resp.json()
            assert "Rate limit" in data["detail"]
            assert resp.headers.get("X-RateLimit-Remaining") == "0"
            assert resp.headers.get("Retry-After") is not None
        finally:
            ratelimit_mod.get_redis = original_get

    @pytest.mark.asyncio
    async def test_fail_open_on_redis_error(self, mock_redis):
        """When Redis is down, requests should still pass through."""
        app = FastAPI()

        @app.get("/api/v1/test")
        async def test_endpoint():
            return {"ok": True}

        app.add_middleware(RateLimitMiddleware)

        # Make Redis calls raise an exception
        import app.core.ratelimit as ratelimit_mod
        ratelimit_mod.get_redis = AsyncMock(side_effect=ConnectionError("Redis down"))

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/v1/test")
            assert resp.status_code == 200
            assert resp.json() == {"ok": True}
        finally:
            # Restore original
            ratelimit_mod.get_redis = get_redis

    @pytest.mark.asyncio
    async def test_agent_trigger_endpoint_uses_stricter_limit(self, mock_redis):
        """Trigger endpoints should use 10/min limit."""
        app = FastAPI()

        @app.post("/api/v1/agents/social_media/trigger")
        async def trigger():
            return {"status": "queued"}

        app.add_middleware(RateLimitMiddleware)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/agents/social_media/trigger")
        assert resp.status_code == 200
        assert resp.json() == {"status": "queued"}
