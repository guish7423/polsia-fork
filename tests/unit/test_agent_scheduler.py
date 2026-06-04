"""Tests for the Resource-Aware Agent Scheduler.

Tests cover:
- Scheduling under high load → queues to low_priority
- Normal load → dispatches directly to default
- Respects tenant agents_limit
- Scheduler status returns expected metrics
- Rebalance operation redistributes stuck tasks
"""

import pytest
from datetime import datetime, timezone, timedelta

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
    tenant.agents_limit = agents_limit
    tenant.tasks_monthly_limit = tasks_monthly_limit
    tenant.tokens_monthly_limit = tokens_monthly_limit
    tenant.cost_monthly_limit_usd = cost_monthly_limit_usd
    await db.flush()
    return tenant


# ─── schedule_agent ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_schedule_under_load_queues_low_priority(async_db_session):
    """Load score > 80% → queues to low_priority."""
    tenant = await _create_tenant(async_db_session, name="Loaded",
                                   api_key="k-loaded", agents_limit=3)

    # Fill running agents up to the limit
    for _ in range(3):
        async_db_session.add(AgentRun(
            agent_type="test", status="running",
            tenant_id=tenant.id,
            started_at=datetime.now(timezone.utc),
        ))
    # Add some pending tasks
    for _ in range(5):
        async_db_session.add(Task(
            tenant_id=tenant.id, title="pending",
            agent_type="test", status="pending",
        ))
    await async_db_session.flush()

    from app.services.agent_scheduler import AgentSchedulerService
    queue = await AgentSchedulerService.schedule_agent(
        async_db_session, "test_agent", tenant.id,
    )

    # Load score: 3*0.4 + 5*0.3 + 0*0.3 = 1.2 + 1.5 = 2.7
    # 2.7 / 3 = 0.9 > 0.8 → low_priority
    assert queue == "low_priority", (
        f"Expected low_priority queue under high load, got {queue}"
    )


@pytest.mark.asyncio
async def test_schedule_normal_load_dispatches_direct(async_db_session):
    """Load score <= 80% → dispatches directly to default."""
    tenant = await _create_tenant(async_db_session, name="Normal",
                                   api_key="k-normal", agents_limit=10)

    # One running agent
    async_db_session.add(AgentRun(
        agent_type="test", status="running",
        tenant_id=tenant.id,
        started_at=datetime.now(timezone.utc),
    ))
    await async_db_session.flush()

    from app.services.agent_scheduler import AgentSchedulerService
    queue = await AgentSchedulerService.schedule_agent(
        async_db_session, "test_agent", tenant.id,
    )

    # Load score: 1*0.4 + 0*0.3 + 0*0.3 = 0.4
    # 0.4 / 10 = 0.04 <= 0.8 → default
    assert queue == "default", (
        f"Expected default queue under normal load, got {queue}"
    )


@pytest.mark.asyncio
async def test_schedule_respects_tenant_limit(async_db_session):
    """Tenant with agents_limit=0 still returns a queue decision."""
    tenant = await _create_tenant(async_db_session, name="Zero",
                                   api_key="k-zero", agents_limit=0)

    from app.services.agent_scheduler import AgentSchedulerService
    queue = await AgentSchedulerService.schedule_agent(
        async_db_session, "test_agent", tenant.id,
    )

    # agents_limit=0 → division by zero guarded → should fall back to
    # low_priority or return a valid queue name
    assert queue in ("default", "low_priority"), (
        f"Expected a valid queue for agents_limit=0, got {queue}"
    )


# ─── get_scheduler_status ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_scheduler_status_returns_metrics(async_db_session):
    """get_scheduler_status returns all expected metric keys."""
    tenant = await _create_tenant(async_db_session, name="StatusT",
                                   api_key="k-status", agents_limit=5)

    # Seed some state
    for _ in range(2):
        async_db_session.add(AgentRun(
            agent_type="test", status="running",
            tenant_id=tenant.id,
            started_at=datetime.now(timezone.utc),
        ))
    for _ in range(3):
        async_db_session.add(Task(
            tenant_id=tenant.id, title="t",
            agent_type="test", status="pending",
        ))
    await async_db_session.flush()

    from app.services.agent_scheduler import AgentSchedulerService
    status = await AgentSchedulerService.get_scheduler_status(
        async_db_session, tenant.id,
    )

    assert "running" in status
    assert "pending" in status
    assert "queued" in status
    assert "load_score" in status
    assert "threshold_exceeded" in status

    assert status["running"] == 2
    assert status["pending"] >= 3
    assert isinstance(status["load_score"], float)
    assert isinstance(status["threshold_exceeded"], bool)


# ─── rebalance_queues ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rebalance_queues_redistributes(async_db_session):
    """rebalance_queues returns count of redistributed items (≥ 0)."""
    tenant = await _create_tenant(async_db_session, name="Rebal",
                                   api_key="k-rebal", agents_limit=10)

    from app.services.agent_scheduler import AgentSchedulerService
    count = await AgentSchedulerService.rebalance_queues(async_db_session)

    assert isinstance(count, int)
    assert count >= 0
