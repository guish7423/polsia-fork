"""Tests for SelfOptimizer auto-apply integration with ConfigTunerService.

Covers:
- optimize_agent triggers ConfigTunerService.auto_tune when suggestion matches
- optimize_agent skips auto-tune when config_tuner_enabled is False
- optimize_agent only auto-applies generation_config_tuning suggestions
"""

import pytest
from datetime import datetime, timezone, timedelta

from app.config import settings
from app.models.agent_run import AgentRun


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


# ─── test: auto-tune triggered ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_optimize_triggers_auto_tune_when_gen_config_suggestion(async_db_session):
    """optimize_agent auto-applies gen config when suggestion is generation_config_tuning."""
    settings.self_optimization_enabled = True
    settings.config_tuner_enabled = True

    tenant = await _create_tenant(async_db_session, name="AutoTuneT",
                                   api_key="k-autotune")
    # High token usage → triggers generation_config_tuning suggestion
    await _seed_agent_runs(async_db_session, tenant.id, "test_agent",
                           count=5, status="completed", tokens_used=500)

    from app.services.self_optimizer import SelfOptimizerService

    log = await SelfOptimizerService.optimize_agent(
        async_db_session, tenant.id, "test_agent",
    )

    assert log is not None
    assert log.adjustment["suggestion"] == "generation_config_tuning"
    # Verify auto-apply stamp
    assert log.adjustment.get("applied") is True
    assert "gen_config_version" in log.adjustment
    assert isinstance(log.adjustment["gen_config_version"], int)

    # Verify AgentGenConfig row was actually created
    from sqlalchemy import select
    from app.models.agent_gen_config import AgentGenConfig
    stmt = select(AgentGenConfig).where(
        AgentGenConfig.tenant_id == tenant.id,
        AgentGenConfig.agent_type == "test_agent",
    )
    rows = (await async_db_session.execute(stmt)).scalars().all()
    assert len(rows) == 1
    assert rows[0].is_active is True
    assert rows[0].temperature < 0.7  # was tuned


# ─── test: auto-tune skipped when tuner disabled ─────────────────────────────


@pytest.mark.asyncio
async def test_optimize_skips_auto_tune_when_config_tuner_disabled(async_db_session):
    """optimize_agent skips auto-tune when config_tuner_enabled is False."""
    settings.self_optimization_enabled = True
    settings.config_tuner_enabled = False

    tenant = await _create_tenant(async_db_session, name="NoTuneT",
                                   api_key="k-notune")
    await _seed_agent_runs(async_db_session, tenant.id, "test_agent",
                           count=5, status="completed", tokens_used=500)

    from app.services.self_optimizer import SelfOptimizerService

    log = await SelfOptimizerService.optimize_agent(
        async_db_session, tenant.id, "test_agent",
    )

    assert log is not None
    assert log.adjustment["suggestion"] == "generation_config_tuning"
    # Should NOT have applied keys since tuner is disabled
    assert "applied" not in log.adjustment
    assert "gen_config_version" not in log.adjustment


# ─── test: only generation_config_tuning triggers auto-apply ──────────────────


@pytest.mark.asyncio
async def test_optimize_only_applies_generation_config_tuning(async_db_session):
    """optimize_agent only auto-applies for generation_config_tuning, not prompt_tuning."""
    settings.self_optimization_enabled = True
    settings.config_tuner_enabled = True

    tenant = await _create_tenant(async_db_session, name="PromptTuneT",
                                   api_key="k-prompttune")
    # Low success rate → triggers prompt_tuning (not generation_config_tuning)
    await _seed_agent_runs(async_db_session, tenant.id, "test_agent",
                           count=3, status="failed", tokens_used=500)

    from app.services.self_optimizer import SelfOptimizerService

    log = await SelfOptimizerService.optimize_agent(
        async_db_session, tenant.id, "test_agent",
    )

    assert log is not None
    assert log.adjustment["suggestion"] == "prompt_tuning"
    # Should NOT have applied keys since suggestion is different
    assert "applied" not in log.adjustment
    assert "gen_config_version" not in log.adjustment
