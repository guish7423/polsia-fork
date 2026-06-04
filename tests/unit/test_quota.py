"""Tests for resource quota system.

Tests cover:
- Agent concurrent run quota enforcement
- Monthly task creation quota
- Token budget tracking
- 80% usage warning threshold
"""

import pytest
from sqlalchemy import select

from app.models.agent_run import AgentRun
from app.models.model_call import ModelCall
from app.models.task import Task


# ─── Helpers ─────────────────────────────────────────────────────────────────

async def _create_tenant(db, name: str, api_key: str,
                         agents_limit: int = 10,
                         tasks_monthly_limit: int = 1000,
                         tokens_monthly_limit: int = 10_000_000,
                         cost_monthly_limit_usd: float = 50.0):
    from app.services.tenant_service import create_tenant
    tenant = await create_tenant(db, name=name, api_key=api_key, plan="starter")
    # Override defaults
    tenant.agents_limit = agents_limit
    tenant.tasks_monthly_limit = tasks_monthly_limit
    tenant.tokens_monthly_limit = tokens_monthly_limit
    tenant.cost_monthly_limit_usd = cost_monthly_limit_usd
    await db.flush()
    return tenant


# ─── check_agent_quota ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_agent_quota_exceeded(async_db_session):
    """agents_limit=0 → blocked with reason."""
    tenant = await _create_tenant(async_db_session, name="Limited",
                                   api_key="k-limited", agents_limit=0)

    from app.services.quota_service import check_agent_quota
    result = await check_agent_quota(async_db_session, tenant.id)

    assert result.allowed is False
    assert result.reason == "agent_limit_exceeded"
    assert result.current == 0
    assert result.limit == 0


@pytest.mark.asyncio
async def test_agent_quota_allowed(async_db_session):
    """agents_limit=10 and no running agents → allowed."""
    tenant = await _create_tenant(async_db_session, name="OK",
                                   api_key="k-ok", agents_limit=10)

    from app.services.quota_service import check_agent_quota
    result = await check_agent_quota(async_db_session, tenant.id)

    assert result.allowed is True
    assert result.current == 0
    assert result.limit == 10


@pytest.mark.asyncio
async def test_agent_quota_counts_running_only(async_db_session):
    """Only 'running' agents count toward the agent quota."""
    tenant = await _create_tenant(async_db_session, name="Mixed",
                                   api_key="k-mixed", agents_limit=2)

    # One completed agent run (doesn't count)
    async_db_session.add(AgentRun(
        agent_type="orch", status="completed",
        tenant_id=tenant.id
    ))
    # One running agent run (counts)
    async_db_session.add(AgentRun(
        agent_type="orch", status="running",
        tenant_id=tenant.id
    ))
    await async_db_session.flush()

    from app.services.quota_service import check_agent_quota
    result = await check_agent_quota(async_db_session, tenant.id)

    assert result.allowed is True  # 1 running < 2 limit
    assert result.current == 1


# ─── check_tasks_monthly_quota ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tasks_monthly_quota_exceeded(async_db_session):
    """tasks_monthly_limit=0 → blocked."""
    tenant = await _create_tenant(async_db_session, name="Blocked",
                                   api_key="k-blocked", tasks_monthly_limit=0)

    from app.services.quota_service import check_tasks_monthly_quota
    result = await check_tasks_monthly_quota(async_db_session, tenant.id)

    assert result.allowed is False
    assert result.reason == "tasks_monthly_limit_exceeded"
    assert result.limit == 0


@pytest.mark.asyncio
async def test_tasks_monthly_quota_allowed(async_db_session):
    """tasks_monthly_limit=1000 and no tasks → allowed."""
    tenant = await _create_tenant(async_db_session, name="OK Tasks",
                                   api_key="k-tasks")

    from app.services.quota_service import check_tasks_monthly_quota
    result = await check_tasks_monthly_quota(async_db_session, tenant.id)

    assert result.allowed is True
    assert result.limit == 1000


# ─── check_token_budget ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_token_budget_exceeded(async_db_session):
    """tokens_monthly_limit=0 → blocked."""
    tenant = await _create_tenant(async_db_session, name="Broke",
                                   api_key="k-broke", tokens_monthly_limit=0)

    from app.services.quota_service import check_token_budget
    result = await check_token_budget(async_db_session, tenant.id)

    assert result.allowed is False
    assert result.reason == "token_budget_exceeded"


@pytest.mark.asyncio
async def test_quota_warning_at_80_percent(async_db_session):
    """800k tokens used out of 1M → allowed but usage_pct > 0.8."""
    tenant = await _create_tenant(async_db_session, name="Almost",
                                   api_key="k-almost",
                                   tokens_monthly_limit=1_000_000)

    # Seed 9 model calls with 90k tokens each = 810k total (> 80% of 1M)
    for _ in range(9):
        async_db_session.add(ModelCall(
            tenant_id=tenant.id,
            provider="test",
            model="test-model",
            input_tokens=45_000,
            output_tokens=45_000,
            cost_usd=0.0,
            duration_ms=100,
            success=True,
        ))
    await async_db_session.flush()

    from app.services.quota_service import check_token_budget
    result = await check_token_budget(async_db_session, tenant.id)

    assert result.allowed is True
    assert result.usage_pct > 0.8
    assert result.current == 810_000
    assert result.limit == 1_000_000


# ─── check_cost_budget ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cost_budget_exceeded(async_db_session):
    """Monthly cost spent > limit → blocked."""
    tenant = await _create_tenant(async_db_session, name="Costly",
                                   api_key="k-costly",
                                   cost_monthly_limit_usd=10.0)

    # Seed 3 model calls totaling $12
    async_db_session.add(ModelCall(
        tenant_id=tenant.id, provider="test", model="test",
        input_tokens=0, output_tokens=0,
        cost_usd=5.0, duration_ms=100, success=True,
    ))
    async_db_session.add(ModelCall(
        tenant_id=tenant.id, provider="test", model="test",
        input_tokens=0, output_tokens=0,
        cost_usd=5.0, duration_ms=100, success=True,
    ))
    async_db_session.add(ModelCall(
        tenant_id=tenant.id, provider="test", model="test",
        input_tokens=0, output_tokens=0,
        cost_usd=2.0, duration_ms=100, success=True,
    ))
    await async_db_session.flush()

    from app.services.quota_service import check_cost_budget
    result = await check_cost_budget(async_db_session, tenant.id)

    assert result.allowed is False
    assert result.reason == "cost_budget_exceeded"
    assert result.current >= 12.0


# ─── get_quota_usage (dashboard snapshot) ─────────────────────────────────────


@pytest.mark.asyncio
async def test_get_quota_usage_returns_all_keys(async_db_session):
    """get_quota_usage returns all four quota dimensions."""
    tenant = await _create_tenant(async_db_session, name="Full",
                                   api_key="k-full")

    from app.services.quota_service import get_quota_usage
    usage = await get_quota_usage(async_db_session, tenant.id)

    assert "agents" in usage
    assert "tasks" in usage
    assert "tokens" in usage
    assert "cost" in usage

    assert usage["agents"].allowed is True
    assert usage["tasks"].allowed is True
    assert usage["tokens"].allowed is True
    assert usage["cost"].allowed is True
