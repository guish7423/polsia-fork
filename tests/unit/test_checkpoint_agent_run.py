"""Tests for AgentRun-level checkpoint persistence (durable execution).

These tests verify that checkpoint state can be persisted to and restored
from the AgentRun SQL record, enabling Celery task retries to skip already-
completed steps after a crash.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from app.core.checkpoint import Checkpoint


@pytest.mark.asyncio
async def test_save_checkpoint_to_agent_run(async_db_session):
    """Checkpoint state can be persisted to AgentRun (SQL)."""
    from app.models.agent_run import AgentRun

    # Create an AgentRun
    run = AgentRun(
        tenant_id=1,
        agent_type="orch",
        status="running",
        input_context={},
    )
    async_db_session.add(run)
    await async_db_session.flush()

    cp = Checkpoint(f"run:{run.id}", ttl=3600)
    await cp.run("step-1", lambda: {"data": "hello"})

    # Persist checkpoint state to DB
    await cp.save_to_db(async_db_session, run.id)

    # Restore from DB
    cp2 = await Checkpoint.restore_from_db(async_db_session, run.id)
    assert cp2 is not None

    restored = await cp2.run("step-1", lambda: None)
    assert restored == {"data": "hello"}  # cached, not re-executed

    # Verify the AgentRun record was updated
    await async_db_session.refresh(run)
    assert run.checkpoint_data is not None
    assert "steps" in run.checkpoint_data
    assert "step-1" in run.checkpoint_data["steps"]
    assert run.checkpoint_data["steps"]["step-1"]["data"] == "hello"


@pytest.mark.asyncio
async def test_restore_from_db_nonexistent_run(async_db_session):
    """restore_from_db returns None for non-existent AgentRun."""
    cp = await Checkpoint.restore_from_db(async_db_session, 99999)
    assert cp is None


@pytest.mark.asyncio
async def test_restore_from_db_no_checkpoint_data(async_db_session):
    """restore_from_db returns None when AgentRun has no checkpoint_data."""
    from app.models.agent_run import AgentRun

    run = AgentRun(
        tenant_id=1,
        agent_type="orch",
        status="running",
        input_context={},
    )
    async_db_session.add(run)
    await async_db_session.flush()

    cp = await Checkpoint.restore_from_db(async_db_session, run.id)
    assert cp is None


@pytest.mark.asyncio
async def test_retry_skips_completed_steps():
    """On retry after crash, completed steps use cached results."""
    call_count = 0

    async def step_fn():
        nonlocal call_count
        call_count += 1
        return call_count

    cp = Checkpoint("retry-test", ttl=3600)
    r1 = await cp.run("step1", step_fn)  # executes
    r2 = await cp.run("step2", step_fn)  # executes
    assert call_count == 2

    # Simulate retry with new checkpoint (same task_id) — uses in-memory fallback
    cp2 = Checkpoint("retry-test", ttl=3600)
    r1b = await cp2.run("step1", lambda: 999)  # cached!
    r2b = await cp2.run("step2", lambda: 999)  # cached!
    assert r1b == 1  # from cache, not 999
    assert r2b == 2  # from cache, not 999


@pytest.mark.asyncio
async def test_save_to_db_with_redis_fallback(async_db_session, monkeypatch):
    """save_to_db works with in-memory fallback when Redis is unavailable."""
    from app.models.agent_run import AgentRun

    # Ensure checkpoint uses in-memory fallback
    monkeypatch.delenv("CHECKPOINT_REDIS_URL", raising=False)
    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)

    run = AgentRun(
        tenant_id=1,
        agent_type="orch",
        status="running",
        input_context={},
    )
    async_db_session.add(run)
    await async_db_session.flush()

    cp = Checkpoint(f"run:{run.id}", ttl=3600)
    await cp.run("alpha", lambda: {"value": 42})
    await cp.run("beta", lambda: ["x", "y"])

    # Save without Redis
    await cp.save_to_db(async_db_session, run.id)

    # Verify multiple steps saved
    await async_db_session.refresh(run)
    assert "alpha" in run.checkpoint_data["steps"]
    assert "beta" in run.checkpoint_data["steps"]
    assert run.checkpoint_data["steps"]["alpha"]["value"] == 42
    assert run.checkpoint_data["steps"]["beta"] == ["x", "y"]


@pytest.mark.asyncio
async def test_save_to_db_missing_run(async_db_session):
    """save_to_db silently handles non-existent AgentRun."""
    cp = Checkpoint("run:99999", ttl=3600)
    await cp.run("step", lambda: 1)

    # Should not raise
    await cp.save_to_db(async_db_session, 99999)
