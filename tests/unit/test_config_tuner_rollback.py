"""Test ConfigTunerService.check_and_rollback — auto-detect degradation + revert."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.agent_gen_config import AgentGenConfig
from app.models.agent_run import AgentRun
from app.models.optimization_log import OptimizationLog
from app.services.config_tuner import ConfigTunerService


@pytest.fixture
def now():
    return datetime.now(timezone.utc)


async def _setup_config_and_runs(
    async_db_session,
    *,
    tenant_id: int = 1,
    agent_type: str = "orchestrator",
    config_version: int = 1,
    is_active: bool = True,
    config_created_at: datetime | None = None,
    rolled_back_at: datetime | None = None,
    pre_statuses: list[str] | None = None,
    pre_tokens: list[int] | None = None,
    post_statuses: list[str] | None = None,
    post_tokens: list[int] | None = None,
):
    """Helper: create baseline config + pre/post AgentRun records.

    Pre records get ``started_at`` before *config_created_at*,
    post records get ``started_at`` after it.
    """
    if config_created_at is None:
        config_created_at = datetime.now(timezone.utc)

    config = AgentGenConfig(
        tenant_id=tenant_id,
        agent_type=agent_type,
        version=config_version,
        temperature=0.7,
        max_tokens=2048,
        is_active=is_active,
        applied_by="auto_tune",
        created_at=config_created_at,
        rolled_back_at=rolled_back_at,
    )
    async_db_session.add(config)

    if pre_statuses:
        for i, s in enumerate(pre_statuses):
            async_db_session.add(AgentRun(
                tenant_id=tenant_id,
                agent_type=agent_type,
                status=s,
                tokens_used=pre_tokens[i] if pre_tokens and i < len(pre_tokens) else 1000,
                started_at=config_created_at - timedelta(hours=len(pre_statuses) - i),
            ))

    if post_statuses:
        for i, s in enumerate(post_statuses):
            async_db_session.add(AgentRun(
                tenant_id=tenant_id,
                agent_type=agent_type,
                status=s,
                tokens_used=post_tokens[i] if post_tokens and i < len(post_tokens) else 1000,
                started_at=config_created_at + timedelta(hours=i + 1),
            ))

    await async_db_session.flush()
    return config


# ── Test 1: absolute degradation triggers rollback ──────────────────────


@pytest.mark.asyncio
async def test_check_and_rollback_triggers_on_absolute_degradation(async_db_session, now):
    """Drop >10pp → reverts to previous version + logs."""
    config_ts = now - timedelta(hours=1)

    # Create v1 (baseline, inactive)
    v1 = AgentGenConfig(
        tenant_id=1, agent_type="orchestrator", version=1,
        temperature=0.7, max_tokens=2048, is_active=False, applied_by="initial",
        created_at=config_ts - timedelta(hours=2),
    )
    # Create v2 (current active — the one to evaluate)
    v2 = AgentGenConfig(
        tenant_id=1, agent_type="orchestrator", version=2,
        temperature=0.6, max_tokens=1536, is_active=True, applied_by="auto_tune",
        created_at=config_ts,
    )
    async_db_session.add_all([v1, v2])
    await async_db_session.flush()

    # Pre-change runs (before v2's created_at)
    for i in range(6):
        async_db_session.add(AgentRun(
            tenant_id=1, agent_type="orchestrator",
            status="completed" if i < 5 else "failed",  # 83.3%
            tokens_used=1000,
            started_at=config_ts - timedelta(hours=6 - i),
        ))

    # Post-change runs (after v2's created_at)
    for i in range(6):
        async_db_session.add(AgentRun(
            tenant_id=1, agent_type="orchestrator",
            status="completed" if i < 2 else "failed",  # 33.3%
            tokens_used=2000,
            started_at=config_ts + timedelta(hours=i + 1),
        ))

    await async_db_session.flush()

    result = await ConfigTunerService.check_and_rollback(
        async_db_session, tenant_id=1, agent_type="orchestrator",
    )

    assert result is True, "Expected rollback to be triggered"

    # v1 should now be active
    active = await ConfigTunerService.get_effective_config(
        async_db_session, tenant_id=1, agent_type="orchestrator",
    )
    assert active["version"] == 1
    assert active["is_active"] is True

    # v2 should be deactivated with rolled_back_at set
    stmt = (
        select(AgentGenConfig)
        .where(
            AgentGenConfig.tenant_id == 1,
            AgentGenConfig.agent_type == "orchestrator",
            AgentGenConfig.version == 2,
        )
    )
    result = await async_db_session.execute(stmt)
    old_config = result.scalar_one()
    assert old_config.is_active is False
    assert old_config.rolled_back_at is not None

    # OptimizationLog should have been created
    log_stmt = (
        select(OptimizationLog)
        .where(
            OptimizationLog.tenant_id == 1,
            OptimizationLog.agent_type == "orchestrator",
        )
        .order_by(OptimizationLog.created_at.desc())
        .limit(1)
    )
    result = await async_db_session.execute(log_stmt)
    log = result.scalar_one()
    assert log.metric == "success_rate"
    assert log.adjustment.get("suggestion") == "rollback"


# ── Test 2: improved metrics → skip ────────────────────────────────────


@pytest.mark.asyncio
async def test_check_and_rollback_skips_when_improved(async_db_session, now):
    """Metrics improved → no rollback."""
    config_ts = now - timedelta(hours=1)

    v1 = AgentGenConfig(
        tenant_id=1, agent_type="orchestrator", version=1,
        temperature=0.7, max_tokens=2048, is_active=False, applied_by="initial",
        created_at=config_ts - timedelta(hours=2),
    )
    v2 = AgentGenConfig(
        tenant_id=1, agent_type="orchestrator", version=2,
        temperature=0.6, max_tokens=1536, is_active=True, applied_by="auto_tune",
        created_at=config_ts,
    )
    async_db_session.add_all([v1, v2])

    # Pre: 3/6 = 50% success rate
    for i in range(6):
        async_db_session.add(AgentRun(
            tenant_id=1, agent_type="orchestrator",
            status="completed" if i < 3 else "failed",
            tokens_used=2000,
            started_at=config_ts - timedelta(hours=6 - i),
        ))
    # Post: 5/6 = 83% success rate (improved), tokens 800 (lower than 2000)
    for i in range(6):
        async_db_session.add(AgentRun(
            tenant_id=1, agent_type="orchestrator",
            status="completed" if i < 5 else "failed",
            tokens_used=800,
            started_at=config_ts + timedelta(hours=i + 1),
        ))

    await async_db_session.flush()

    result = await ConfigTunerService.check_and_rollback(
        async_db_session, tenant_id=1, agent_type="orchestrator",
    )

    assert result is False, "No rollback expected when metrics improved"


# ── Test 3: insufficient data → skip ───────────────────────────────────


@pytest.mark.asyncio
async def test_check_and_rollback_insufficient_data_skips(async_db_session, now):
    """<5 post-change records → skip."""
    config_ts = now - timedelta(hours=1)

    config = AgentGenConfig(
        tenant_id=1, agent_type="orchestrator", version=1,
        temperature=0.6, max_tokens=1536, is_active=True, applied_by="auto_tune",
        created_at=config_ts,
    )
    async_db_session.add(config)

    # Pre: 6 records
    for i in range(6):
        async_db_session.add(AgentRun(
            tenant_id=1, agent_type="orchestrator",
            status="completed",
            tokens_used=1000,
            started_at=config_ts - timedelta(hours=6 - i),
        ))
    # Post: only 3 records (< 5 minimum)
    for i in range(3):
        async_db_session.add(AgentRun(
            tenant_id=1, agent_type="orchestrator",
            status="failed",
            tokens_used=3000,
            started_at=config_ts + timedelta(hours=i + 1),
        ))

    await async_db_session.flush()

    result = await ConfigTunerService.check_and_rollback(
        async_db_session, tenant_id=1, agent_type="orchestrator",
    )

    assert result is False, "No rollback with insufficient data"


# ── Test 4: cooldown → skip ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_check_and_rollback_cooldown_skips(async_db_session, now):
    """rolled_back_at within 7 days → skip."""
    config_ts = now - timedelta(hours=1)

    # Config that was rolled back 1 day ago (within 7-day cooldown)
    config = AgentGenConfig(
        tenant_id=1, agent_type="orchestrator", version=1,
        temperature=0.6, max_tokens=1536, is_active=True, applied_by="auto_tune",
        created_at=config_ts,
        rolled_back_at=now - timedelta(days=1),
    )
    async_db_session.add(config)

    # 6 post records with terrible metrics
    for i in range(6):
        async_db_session.add(AgentRun(
            tenant_id=1, agent_type="orchestrator",
            status="failed",
            tokens_used=5000,
            started_at=config_ts + timedelta(hours=i + 1),
        ))

    await async_db_session.flush()

    result = await ConfigTunerService.check_and_rollback(
        async_db_session, tenant_id=1, agent_type="orchestrator",
    )

    assert result is False, "No rollback during cooldown"
