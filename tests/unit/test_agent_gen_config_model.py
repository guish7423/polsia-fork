"""Test AgentGenConfig model CRUD and defaults."""

import pytest
from sqlalchemy import select

from app.models.agent_gen_config import AgentGenConfig
from app.models.optimization_log import OptimizationLog
from app.models.tenant import Tenant


@pytest.mark.asyncio
async def test_create_agent_gen_config(async_db_session):
    """Create AgentGenConfig with all fields."""
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
    await async_db_session.refresh(config)

    assert config.id is not None
    assert config.tenant_id == 1
    assert config.agent_type == "orchestrator"
    assert config.version == 1
    assert config.temperature == 0.7
    assert config.max_tokens == 2048
    assert config.top_p == 0.9
    assert config.is_active is True
    assert config.applied_by == "initial"
    assert config.optimization_log_id is None
    assert config.rolled_back_at is None
    assert config.created_at is not None


@pytest.mark.asyncio
async def test_agent_gen_config_nullable_params(async_db_session):
    """All generation params are nullable."""
    config = AgentGenConfig(
        tenant_id=1,
        agent_type="finance",
        version=1,
        applied_by="initial",
    )
    async_db_session.add(config)
    await async_db_session.flush()

    assert config.temperature is None
    assert config.max_tokens is None
    assert config.top_p is None


@pytest.mark.asyncio
async def test_agent_gen_config_default_is_active(async_db_session):
    """is_active defaults to True."""
    config = AgentGenConfig(
        tenant_id=1,
        agent_type="social_media",
        version=1,
        applied_by="initial",
    )
    async_db_session.add(config)
    await async_db_session.flush()

    assert config.is_active is True


@pytest.mark.asyncio
async def test_agent_gen_config_unique_constraint(async_db_session):
    """Duplicate (tenant_id, agent_type, version) raises IntegrityError."""
    from sqlalchemy.exc import IntegrityError

    config1 = AgentGenConfig(
        tenant_id=1,
        agent_type="orchestrator",
        version=1,
        applied_by="initial",
    )
    config2 = AgentGenConfig(
        tenant_id=1,
        agent_type="orchestrator",
        version=1,
        applied_by="auto_tune",
    )
    async_db_session.add_all([config1, config2])
    with pytest.raises(IntegrityError):
        await async_db_session.flush()


@pytest.mark.asyncio
async def test_agent_gen_config_different_tenant_same_version(async_db_session):
    """Same (agent_type, version) for different tenant_id is allowed."""
    c1 = AgentGenConfig(
        tenant_id=1, agent_type="orchestrator", version=1, applied_by="initial",
    )
    c2 = AgentGenConfig(
        tenant_id=2, agent_type="orchestrator", version=1, applied_by="auto_tune",
    )
    async_db_session.add_all([c1, c2])
    await async_db_session.flush()

    result = await async_db_session.execute(
        select(AgentGenConfig).order_by(AgentGenConfig.tenant_id)
    )
    configs = result.scalars().all()
    assert len(configs) == 2


@pytest.mark.asyncio
async def test_agent_gen_config_query_by_tenant_agent_type(async_db_session):
    """Query active config by tenant_id + agent_type."""
    config = AgentGenConfig(
        tenant_id=1,
        agent_type="orchestrator",
        version=2,
        temperature=0.5,
        applied_by="auto_tune",
    )
    async_db_session.add(config)
    await async_db_session.flush()

    result = await async_db_session.execute(
        select(AgentGenConfig).where(
            AgentGenConfig.tenant_id == 1,
            AgentGenConfig.agent_type == "orchestrator",
            AgentGenConfig.is_active.is_(True),
        )
    )
    found = result.scalar_one_or_none()
    assert found is not None
    assert found.version == 2
    assert found.temperature == 0.5
