"""Test AgentStreamManager ring buffer and SSE streaming."""
import json
import pytest

from app.core.agent_stream import AgentStreamManager


@pytest.fixture
def manager():
    """Fresh manager for each test (no singleton interference)."""
    m = AgentStreamManager(max_buffer=100)
    return m


@pytest.mark.asyncio
async def test_publish_and_recent_steps(manager):
    """publish_step adds to ring buffer; get_recent_steps retrieves them."""
    manager.publish_step("test_agent", "thinking", "Analyzing input...", "ts-1")
    manager.publish_step("test_agent", "tool_call", "Searching DB...", "ts-2")
    manager.publish_step("test_agent", "llm_start", "Calling LLM...", "ts-3")

    steps = manager.get_recent_steps("test_agent", limit=10)
    assert len(steps) == 3
    assert steps[0]["step"] == "thinking"
    assert steps[0]["content"] == "Analyzing input..."
    assert steps[1]["step"] == "tool_call"
    assert steps[2]["step"] == "llm_start"


@pytest.mark.asyncio
async def test_stream_steps_returns_history_first(manager):
    """stream_steps yields existing history before waiting for live events."""
    manager.publish_step("test_agent", "thinking", "Historic step", "ts-0")

    gen = manager.stream_steps("test_agent")
    first = await gen.__anext__()

    assert first["step"] == "thinking"
    assert first["content"] == "Historic step"

    # Clean up the generator (disconnect)
    await gen.aclose()


@pytest.mark.asyncio
async def test_stream_steps_delivers_live_events(manager):
    """stream_steps yields events published after subscription."""
    gen = manager.stream_steps("test_agent")

    manager.publish_step("test_agent", "llm_start", "Starting LLM...", "ts-live")

    event = await gen.__anext__()
    assert event["step"] == "llm_start"
    assert event["content"] == "Starting LLM..."

    await gen.aclose()


@pytest.mark.asyncio
async def test_ring_buffer_respects_maxlen(manager):
    """Ring buffer never exceeds max_buffer (100)."""
    for i in range(150):
        manager.publish_step("test_agent", "thinking", f"Step {i}", f"ts-{i}")

    steps = manager.get_recent_steps("test_agent", limit=200)
    assert len(steps) == 100  # maxlen enforced
    assert steps[0]["content"] == "Step 50"  # oldest survivor
    assert steps[-1]["content"] == "Step 149"  # newest


def test_sse_route_registered():
    """The SSE route /agents/{agent_type}/stream is registered exactly once."""
    from app.api.v1.agents import router

    paths = [getattr(r, "path", "") for r in router.routes]
    assert paths.count("/agents/{agent_type}/stream") == 1
