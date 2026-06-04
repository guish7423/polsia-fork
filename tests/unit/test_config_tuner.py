"""Test ConfigTunerService — auto-applies optimization suggestions as AgentGenConfig versions."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.config import settings
from app.models.agent_gen_config import AgentGenConfig
from app.services.config_tuner import ConfigTunerService


@pytest.mark.asyncio
async def test_get_effective_config_returns_empty_when_no_config(async_db_session):
    """No config exists → returns {} (not defaults)."""
    result = await ConfigTunerService.get_effective_config(
        async_db_session, tenant_id=1, agent_type="orchestrator",
    )
    assert result == {}


@pytest.mark.asyncio
async def test_get_effective_config_returns_active_config(async_db_session):
    """Active config exists → returns its dict representation."""
    config = AgentGenConfig(
        tenant_id=1,
        agent_type="orchestrator",
        version=1,
        temperature=0.7,
        max_tokens=2048,
        top_p=0.9,
        is_active=True,
        applied_by="initial",
    )
    async_db_session.add(config)
    await async_db_session.flush()

    result = await ConfigTunerService.get_effective_config(
        async_db_session, tenant_id=1, agent_type="orchestrator",
    )
    assert result["temperature"] == 0.7
    assert result["max_tokens"] == 2048
    assert result["top_p"] == 0.9


@pytest.mark.asyncio
async def test_apply_generation_config_creates_new_version(async_db_session):
    """apply_generation_config creates a new version with reduced values."""
    # Create baseline config
    config = AgentGenConfig(
        tenant_id=1,
        agent_type="orchestrator",
        version=1,
        temperature=0.7,
        max_tokens=2048,
        top_p=0.9,
        is_active=True,
        applied_by="initial",
    )
    async_db_session.add(config)
    await async_db_session.flush()

    new_config = await ConfigTunerService.apply_generation_config(
        async_db_session,
        tenant_id=1,
        agent_type="orchestrator",
        suggestion={"suggestion": "generation_config_tuning"},
    )

    assert new_config.version == 2  # version auto-incremented
    assert new_config.temperature == 0.6  # 0.7 - 0.1
    assert new_config.max_tokens == 1536  # 2048 - 512
    assert new_config.top_p == 0.9  # preserved from baseline
    assert new_config.is_active is True
    assert new_config.applied_by == "auto_tune"


@pytest.mark.asyncio
async def test_apply_deactivates_previous_version(async_db_session):
    """After apply, the previous active version is deactivated."""
    config = AgentGenConfig(
        tenant_id=1,
        agent_type="orchestrator",
        version=1,
        temperature=0.7,
        max_tokens=2048,
        is_active=True,
        applied_by="initial",
    )
    async_db_session.add(config)
    await async_db_session.flush()

    await ConfigTunerService.apply_generation_config(
        async_db_session,
        tenant_id=1,
        agent_type="orchestrator",
        suggestion={},
    )

    # Check previous version is deactivated
    result = await async_db_session.execute(
        select(AgentGenConfig).where(
            AgentGenConfig.tenant_id == 1,
            AgentGenConfig.agent_type == "orchestrator",
            AgentGenConfig.version == 1,
        )
    )
    old = result.scalar_one()
    assert old.is_active is False

    # Check new version is active
    result = await async_db_session.execute(
        select(AgentGenConfig).where(
            AgentGenConfig.tenant_id == 1,
            AgentGenConfig.agent_type == "orchestrator",
            AgentGenConfig.version == 2,
        )
    )
    new = result.scalar_one()
    assert new.is_active is True


@pytest.mark.asyncio
async def test_revert_config_reactivates_previous(async_db_session):
    """revert_config without target_version reactivates the previous version."""
    # Create v1 (will become previous)
    v1 = AgentGenConfig(
        tenant_id=1,
        agent_type="orchestrator",
        version=1,
        temperature=0.7,
        max_tokens=2048,
        is_active=False,
        applied_by="initial",
    )
    # Create v2 (current active)
    v2 = AgentGenConfig(
        tenant_id=1,
        agent_type="orchestrator",
        version=2,
        temperature=0.6,
        max_tokens=1536,
        is_active=True,
        applied_by="auto_tune",
    )
    async_db_session.add_all([v1, v2])
    await async_db_session.flush()

    reverted = await ConfigTunerService.revert_config(
        async_db_session, tenant_id=1, agent_type="orchestrator",
    )

    # Should have reactivated v1
    assert reverted.version == 1
    assert reverted.is_active is True

    # v2 should be deactivated and have rolled_back_at set
    result = await async_db_session.execute(
        select(AgentGenConfig).where(
            AgentGenConfig.tenant_id == 1,
            AgentGenConfig.agent_type == "orchestrator",
            AgentGenConfig.version == 2,
        )
    )
    old = result.scalar_one()
    assert old.is_active is False
    assert old.rolled_back_at is not None


@pytest.mark.asyncio
async def test_revert_config_target_version(async_db_session):
    """revert_config with target_version restores that specific version."""
    v1 = AgentGenConfig(
        tenant_id=1, agent_type="orchestrator", version=1,
        temperature=0.7, max_tokens=2048, is_active=False, applied_by="initial",
    )
    v2 = AgentGenConfig(
        tenant_id=1, agent_type="orchestrator", version=2,
        temperature=0.6, max_tokens=1536, is_active=False, applied_by="auto_tune",
    )
    v3 = AgentGenConfig(
        tenant_id=1, agent_type="orchestrator", version=3,
        temperature=0.5, max_tokens=1024, is_active=True, applied_by="auto_tune",
    )
    async_db_session.add_all([v1, v2, v3])
    await async_db_session.flush()

    reverted = await ConfigTunerService.revert_config(
        async_db_session, tenant_id=1, agent_type="orchestrator", target_version=2,
    )

    assert reverted.version == 2
    assert reverted.is_active is True

    # v3 should be deactivated
    result = await async_db_session.execute(
        select(AgentGenConfig).where(
            AgentGenConfig.tenant_id == 1,
            AgentGenConfig.agent_type == "orchestrator",
            AgentGenConfig.version == 3,
        )
    )
    old = result.scalar_one()
    assert old.is_active is False
    assert old.rolled_back_at is not None


@pytest.mark.asyncio
async def test_auto_tune_skipped_when_disabled(async_db_session):
    """auto_tune returns None when config_tuner_enabled is False."""
    original = settings.config_tuner_enabled
    settings.config_tuner_enabled = False
    try:
        result = await ConfigTunerService.auto_tune(
            async_db_session,
            tenant_id=1,
            agent_type="orchestrator",
            suggestion={"suggestion": "generation_config_tuning"},
        )
        assert result is None
    finally:
        settings.config_tuner_enabled = original
