"""Tests for Agent Self-Optimization.

Tests cover:
- analyze_agent_performance returns expected metrics
- optimize_agent creates OptimizationLog
- optimize_agent is skipped when self_optimization_enabled=False
- optimize_agent respects 24h cooldown (already optimized recently)
- get_optimization_history returns scoped and unscoped results
"""

import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from app.models.agent_run import AgentRun
from app.models.tenant import Tenant


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


async def _seed_agent_runs(db, tenant_id: int, agent_type: str,
                           count: int = 5,
                           status: str = "completed",
                           duration_secs: float = 10.0,
                           tokens_used: int = 500):
    """Helper to seed AgentRun records."""
    for i in range(count):
        db.add(AgentRun(
            agent_type=agent_type,
            tenant_id=tenant_id,
            status=status,
            duration_secs=duration_secs,
            tokens_used=tokens_used,
            started_at=datetime.now(timezone.utc) - timedelta(hours=i),
        ))
    await db.flush()


# ─── analyze_agent_performance ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_analyze_agent_performance_returns_metrics(async_db_session):
    """analyze_agent_performance returns all expected metric keys."""
    tenant = await _create_tenant(async_db_session, name="PerfT",
                                   api_key="k-perf", agents_limit=10)
    await _seed_agent_runs(async_db_session, tenant.id, "test_agent",
                           count=5, status="completed", duration_secs=10.0)

    from app.services.self_optimizer import SelfOptimizerService

    metrics = await SelfOptimizerService.analyze_agent_performance(
        async_db_session, tenant.id, "test_agent",
    )

    assert "success_rate" in metrics
    assert "avg_duration_ms" in metrics
    assert "avg_tokens_per_run" in metrics
    assert "token_efficiency" in metrics
    assert "total_runs" in metrics

    assert metrics["total_runs"] == 5
    assert metrics["success_rate"] == 1.0  # all completed
    assert isinstance(metrics["avg_duration_ms"], float)
    assert metrics["avg_tokens_per_run"] == 500
    assert isinstance(metrics["token_efficiency"], float)


@pytest.mark.asyncio
async def test_analyze_performance_with_failures(async_db_session):
    """analyze_agent_performance correctly calculates success rate with failures."""
    tenant = await _create_tenant(async_db_session, name="FailT",
                                   api_key="k-fail", agents_limit=10)
    await _seed_agent_runs(async_db_session, tenant.id, "test_agent",
                           count=3, status="completed", duration_secs=10.0)
    await _seed_agent_runs(async_db_session, tenant.id, "test_agent",
                           count=2, status="failed", duration_secs=5.0)

    from app.services.self_optimizer import SelfOptimizerService

    metrics = await SelfOptimizerService.analyze_agent_performance(
        async_db_session, tenant.id, "test_agent",
    )

    assert metrics["total_runs"] == 5
    assert metrics["success_rate"] == 0.6  # 3/5
    assert metrics["avg_tokens_per_run"] == 500


# ─── optimize_agent ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_optimize_agent_creates_optimization_log(async_db_session):
    """optimize_agent creates an OptimizationLog entry."""
    from app.config import settings
    settings.self_optimization_enabled = True

    tenant = await _create_tenant(async_db_session, name="OptT",
                                   api_key="k-opt", agents_limit=10)
    await _seed_agent_runs(async_db_session, tenant.id, "test_agent",
                           count=3, status="completed", duration_secs=10.0)

    from app.services.self_optimizer import SelfOptimizerService

    log = await SelfOptimizerService.optimize_agent(
        async_db_session, tenant.id, "test_agent",
    )

    assert log is not None
    assert log.tenant_id == tenant.id
    assert log.agent_type == "test_agent"
    assert log.metric in ("success_rate", "avg_duration", "token_efficiency")
    assert isinstance(log.before_value, float)
    assert isinstance(log.after_value, float)
    assert isinstance(log.adjustment, dict)
    assert log.created_at is not None


@pytest.mark.asyncio
async def test_optimize_agent_skipped_when_disabled(async_db_session):
    """optimize_agent returns None when self_optimization_enabled=False."""
    from app.config import settings
    settings.self_optimization_enabled = False

    tenant = await _create_tenant(async_db_session, name="DisabledT",
                                   api_key="k-disabled", agents_limit=10)
    await _seed_agent_runs(async_db_session, tenant.id, "test_agent",
                           count=3, status="completed")

    from app.services.self_optimizer import SelfOptimizerService

    log = await SelfOptimizerService.optimize_agent(
        async_db_session, tenant.id, "test_agent",
    )

    assert log is None


@pytest.mark.asyncio
async def test_optimize_agent_respects_24h_cooldown(async_db_session):
    """optimize_agent returns existing log when already optimized < 24h ago."""
    from app.config import settings
    settings.self_optimization_enabled = True

    tenant = await _create_tenant(async_db_session, name="CoolT",
                                   api_key="k-cool", agents_limit=10)
    await _seed_agent_runs(async_db_session, tenant.id, "test_agent",
                           count=3, status="completed")

    from app.models.optimization_log import OptimizationLog
    from app.services.self_optimizer import SelfOptimizerService

    # Create a recent optimization log
    recent = OptimizationLog(
        tenant_id=tenant.id,
        agent_type="test_agent",
        metric="success_rate",
        before_value=0.8,
        after_value=0.9,
        adjustment={"suggestion": "prompt_tuning"},
    )
    async_db_session.add(recent)
    await async_db_session.flush()

    # Second call should return existing log (cooldown)
    log = await SelfOptimizerService.optimize_agent(
        async_db_session, tenant.id, "test_agent",
    )

    assert log is not None
    assert log.id == recent.id  # Same entry returned


# ─── get_optimization_history ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_optimization_history_returns_logs(async_db_session):
    """get_optimization_history returns all logs for a tenant."""
    from app.config import settings
    settings.self_optimization_enabled = True

    tenant = await _create_tenant(async_db_session, name="HistT",
                                   api_key="k-hist", agents_limit=10)
    await _seed_agent_runs(async_db_session, tenant.id, "test_agent",
                           count=3, status="completed")

    from app.services.self_optimizer import SelfOptimizerService

    # Run optimization to create a log
    log = await SelfOptimizerService.optimize_agent(
        async_db_session, tenant.id, "test_agent",
    )
    assert log is not None

    # Query history
    history = await SelfOptimizerService.get_optimization_history(
        async_db_session, tenant.id,
    )

    assert len(history) >= 1
    assert any(h.id == log.id for h in history)


@pytest.mark.asyncio
async def test_get_optimization_history_filters_by_agent_type(async_db_session):
    """get_optimization_history with agent_type filters results."""
    from app.config import settings
    settings.self_optimization_enabled = True

    tenant = await _create_tenant(async_db_session, name="FilterT",
                                   api_key="k-filter", agents_limit=10)
    await _seed_agent_runs(async_db_session, tenant.id, "type_a",
                           count=3, status="completed")
    await _seed_agent_runs(async_db_session, tenant.id, "type_b",
                           count=3, status="completed")

    from app.services.self_optimizer import SelfOptimizerService

    # Create logs for both types
    log_a = await SelfOptimizerService.optimize_agent(
        async_db_session, tenant.id, "type_a",
    )
    # Create a tenant with different runs for type_b
    log_b = await SelfOptimizerService.optimize_agent(
        async_db_session, tenant.id, "type_b",
    )

    # Filter by type_a
    history = await SelfOptimizerService.get_optimization_history(
        async_db_session, tenant.id, agent_type="type_a",
    )

    assert len(history) >= 1
    assert all(h.agent_type == "type_a" for h in history)
