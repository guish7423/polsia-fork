"""Tests for active quota enforcement — hard reject + middleware gate.

Tests cover:
- task_service.create_task() hard rejection via HTTPException(429)
- model_usage_service.record_model_call() skip when quota exceeded
- QuotaEnforcementMiddleware block/allow for agent runs
"""

import json
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.core.tenant_context import TenantContext, set_current_tenant
from app.models.task import Task


# ─── Helpers ─────────────────────────────────────────────────────────────────

async def _create_tenant(db, name: str, api_key: str,
                         agents_limit: int = 10,
                         tasks_monthly_limit: int = 1000,
                         tokens_monthly_limit: int = 10_000_000,
                         cost_monthly_limit_usd: float = 50.0):
    from app.services.tenant_service import create_tenant
    tenant = await create_tenant(db, name=name, api_key=api_key, plan="starter")
    tenant.agents_limit = agents_limit
    tenant.tasks_monthly_limit = tasks_monthly_limit
    tenant.tokens_monthly_limit = tokens_monthly_limit
    tenant.cost_monthly_limit_usd = cost_monthly_limit_usd
    await db.flush()
    return tenant


# ─── create_task quota enforcement ───────────────────────────────────────────


class TestCreateTaskQuotaEnforcement:
    """task_service.create_task() must hard-reject when quota is exceeded."""

    @pytest.mark.asyncio
    async def test_create_task_rejects_when_quota_exceeded(self, async_db_session):
        """tasks_monthly_limit=0 → HTTPException 429."""
        tenant = await _create_tenant(
            async_db_session, name="Over",
            api_key="k-over", tasks_monthly_limit=0,
        )

        from app.services.task_service import create_task

        # Enable quota for this test
        settings.quota_enabled = True
        try:
            with pytest.raises(HTTPException) as exc_info:
                await create_task(
                    async_db_session,
                    title="Blocked task",
                    agent_type="social_media",
                    tenant_id=tenant.id,
                )
            assert exc_info.value.status_code == 429
            assert exc_info.value.detail == "monthly_task_limit_exceeded"
        finally:
            settings.quota_enabled = False

    @pytest.mark.asyncio
    async def test_create_task_allows_when_under_quota(self, async_db_session):
        """Under limit with quota enabled → task created normally."""
        tenant = await _create_tenant(
            async_db_session, name="Under",
            api_key="k-under", tasks_monthly_limit=1000,
        )

        from app.services.task_service import create_task

        settings.quota_enabled = True
        try:
            task = await create_task(
                async_db_session,
                title="Allowed task",
                agent_type="social_media",
                tenant_id=tenant.id,
            )
            await async_db_session.commit()
            assert task.id is not None
            assert task.title == "Allowed task"
            assert task.status == "pending"
        finally:
            settings.quota_enabled = False


# ─── QuotaEnforcementMiddleware ──────────────────────────────────────────────


class TestQuotaEnforcementMiddleware:
    """QuotaEnforcementMiddleware blocks/permits at HTTP layer."""

    @pytest.mark.asyncio
    async def test_middleware_blocks_agent_run_when_quota_exceeded(self):
        """POST to agent run path → 429 when agent quota exceeded."""
        from app.core import quota_middleware as qm

        app = FastAPI()

        @app.post("/api/v1/agents/runs")
        async def create_run():
            return {"ok": True}

        app.add_middleware(qm.QuotaEnforcementMiddleware)

        # Seed tenant context with a limited tenant
        set_current_tenant(TenantContext(
            id=1, name="Limited", plan="starter",
            api_key="k", agents_limit=0, tasks_monthly_limit=0,
            tokens_monthly_limit=0, cost_monthly_limit_usd=0.0,
            rpm_limit=10, active=True,
        ))

        # Mock check_agent_quota to return blocked
        mock_result = AsyncMock()
        mock_result.allowed = False
        mock_result.reason = "agent_limit_exceeded"
        qm.check_agent_quota = AsyncMock(return_value=mock_result)

        settings.quota_middleware_enabled = True
        original_factory = qm.async_session

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/api/v1/agents/runs")

            assert resp.status_code == 429
            data = resp.json()
            assert data["detail"] == "agent_limit_exceeded"
        finally:
            qm.check_agent_quota = None  # reset
            qm.async_session = original_factory
            settings.quota_middleware_enabled = False

    @pytest.mark.asyncio
    async def test_middleware_skips_when_quota_disabled(self):
        """quota_middleware_enabled=False → request passes through."""
        from app.core import quota_middleware as qm

        app = FastAPI()

        @app.post("/api/v1/agents/runs")
        async def create_run():
            return {"ok": True}

        app.add_middleware(qm.QuotaEnforcementMiddleware)

        set_current_tenant(TenantContext(
            id=1, name="Test", plan="starter",
            api_key="k", agents_limit=1, tasks_monthly_limit=100,
            tokens_monthly_limit=1000, cost_monthly_limit_usd=10.0,
            rpm_limit=10, active=True,
        ))

        settings.quota_middleware_enabled = False

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/api/v1/agents/runs")

            assert resp.status_code == 200
            assert resp.json() == {"ok": True}
        finally:
            settings.quota_middleware_enabled = False


# ─── model_usage quota enforcement ───────────────────────────────────────────


class TestModelCallQuotaEnforcement:
    """record_model_call must skip when token/cost budget exceeded."""

    @pytest.mark.asyncio
    async def test_model_call_skipped_when_token_quota_exceeded(self, async_db_session):
        """tokens_monthly_limit=0 → call skipped, returns None."""
        tenant = await _create_tenant(
            async_db_session, name="NoTokens",
            api_key="k-nt", tokens_monthly_limit=0,
        )

        from app.services.model_usage_service import record_model_call

        settings.quota_enabled = True
        try:
            result = await record_model_call(
                async_db_session,
                provider="test",
                model="test-model",
                input_tokens=100,
                output_tokens=50,
                cost_usd=0.01,
                duration_ms=100,
                success=True,
                tenant_id=tenant.id,
            )
            # Should be None — skipped due to quota
            assert result is None
        finally:
            settings.quota_enabled = False
