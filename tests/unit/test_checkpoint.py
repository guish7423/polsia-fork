"""Tests for step-level checkpointing (app/core/checkpoint.py).

These tests verify the checkpoint logic using the in-memory fallback store,
without requiring a running Redis instance.
"""

from __future__ import annotations

import pytest

from app.core.checkpoint import Checkpoint, clear_checkpoint, get_checkpoint


@pytest.mark.asyncio
async def test_checkpoint_enabled_without_redis() -> None:
    """Without REDIS_URL, _enabled() returns False, but run() still works
    via the in-memory fallback store."""
    cp = Checkpoint("test-task-1", ttl=60)
    assert cp._enabled() is False  # no Redis URL in test env

    # Should still run the function normally
    result = await cp.run("step1", lambda: 42)
    assert result == 42


@pytest.mark.asyncio
async def test_checkpoint_skips_completed_step() -> None:
    """On first call, the function executes.  On second call (same step name),
    the cached result is returned and the function is NOT called again."""
    call_count = 0

    async def expensive_fn() -> dict:
        nonlocal call_count
        call_count += 1
        return {"value": call_count}

    cp = Checkpoint("test-skip", ttl=60)

    # First call — executes
    result1 = await cp.run("expensive", expensive_fn)
    assert result1 == {"value": 1}
    assert call_count == 1

    # Second call — should use cache, function NOT called
    result2 = await cp.run("expensive", expensive_fn)
    assert result2 == {"value": 1}  # still 1, not 2
    assert call_count == 1  # function not called again


@pytest.mark.asyncio
async def test_different_steps_independent() -> None:
    """Different step names are cached independently."""
    cp = Checkpoint("test-independent", ttl=60)

    r1 = await cp.run("step-a", lambda: "alpha")
    r2 = await cp.run("step-b", lambda: "beta")

    assert r1 == "alpha"
    assert r2 == "beta"

    # Re-running step-a still returns cached value
    r3 = await cp.run("step-a", lambda: "gamma")
    assert r3 == "alpha"  # cached, not "gamma"


@pytest.mark.asyncio
async def test_different_task_ids_independent() -> None:
    """Checkpoints for different task IDs do not interfere."""
    cp1 = Checkpoint("task-1", ttl=60)
    cp2 = Checkpoint("task-2", ttl=60)

    await cp1.run("step", lambda: "from-task-1")
    result = await cp2.run("step", lambda: "from-task-2")

    assert result == "from-task-2"


@pytest.mark.asyncio
async def test_checkpoint_key_format() -> None:
    cp = Checkpoint("my-task", ttl=60)
    key = cp.checkpoint_key("my-step")
    assert key == "checkpoint:my-task:my-step"


@pytest.mark.asyncio
async def test_async_function_supported() -> None:
    """Checkpoint accepts both sync and async functions."""

    async def async_fn() -> str:
        return "async-result"

    cp = Checkpoint("test-async", ttl=60)
    result = await cp.run("step", async_fn)
    assert result == "async-result"


@pytest.mark.asyncio
async def test_ttl_eviction() -> None:
    """When TTL expires, the fallback store should not return the value."""
    cp = Checkpoint("test-ttl", ttl=0)  # 0 second TTL

    await cp.run("step", lambda: 100)

    # With ttl=0, the stored value should already be expired
    cached = await cp._load("step")
    assert cached is None, "TTL=0 should cause immediate eviction"


@pytest.mark.asyncio
async def test_factory_cache() -> None:
    """get_checkpoint() returns the same instance for the same task_id."""
    cp1 = get_checkpoint("factory-task", ttl=60)
    cp2 = get_checkpoint("factory-task", ttl=60)
    assert cp1 is cp2  # same object

    clear_checkpoint("factory-task")
    cp3 = get_checkpoint("factory-task", ttl=60)
    assert cp3 is not cp1  # new instance after clear


@pytest.mark.asyncio
async def test_complex_data_types() -> None:
    """Checkpoint supports dicts, lists, nested structures."""
    cp = Checkpoint("test-complex", ttl=60)

    data = {"users": [{"name": "Alice", "score": 95}, {"name": "Bob", "score": 87}]}
    result = await cp.run("fetch", lambda: data)
    assert result == data
    assert result["users"][0]["name"] == "Alice"

    # Cached version should match
    cached = await cp.run("fetch", lambda: {"changed": True})
    assert cached == data  # still original, not changed
