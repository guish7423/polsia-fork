"""AgentStreamManager — in-memory ring buffer per agent_type, publish/subscribe.

Every agent type gets a ring buffer (max 100 messages).  Callers publish
step events with ``publish_step()``, consumers subscribe via the async
generator ``stream_steps()`` which first replays history then delivers
live events over an ``asyncio.Queue`` per connection.  Disconnected
connections are cleaned up automatically.

Usage::

    from app.core.agent_stream import AgentStreamManager

    mgr = AgentStreamManager.get_instance()
    mgr.publish_step("supervisor", "thinking", "Analyzing...")
    async for step in mgr.stream_steps("supervisor"):
        print(step)
"""

import asyncio
from collections import deque
from datetime import datetime, timezone


class AgentStreamManager:
    """In-memory step-event manager per agent type.

    Thread-safe within a single event loop (all operations are
    synchronous — no locking required).
    """

    _instance: "AgentStreamManager | None" = None

    def __init__(self, max_buffer: int = 100) -> None:
        self._max_buffer = max_buffer
        self._buffers: dict[str, deque[dict]] = {}
        self._queues: dict[str, list[asyncio.Queue]] = {}

    # ── Singleton ─────────────────────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> "AgentStreamManager":
        """Return the global singleton (created on first call)."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Internal helpers ──────────────────────────────────────────────────

    def _buffer(self, agent_type: str) -> deque:
        if agent_type not in self._buffers:
            self._buffers[agent_type] = deque(maxlen=self._max_buffer)
        return self._buffers[agent_type]

    def _subscriber_queues(self, agent_type: str) -> list[asyncio.Queue]:
        if agent_type not in self._queues:
            self._queues[agent_type] = []
        return self._queues[agent_type]

    # ── Public API ────────────────────────────────────────────────────────

    def publish_step(
        self,
        agent_type: str,
        step_type: str,
        content: str,
        timestamp: str | None = None,
    ) -> None:
        """Append a step event to the ring buffer and fan-out to listeners.

        Args:
            agent_type: Which agent produced this step.
            step_type: Short label — ``"thinking"``, ``"tool_call"``,
                ``"llm_start"``, ``"llm_end"``, etc.
            content: Human-readable description.
            timestamp: ISO-8601 string.  ``None`` → current time.
        """
        step: dict = {
            "step": step_type,
            "content": content,
            "ts": timestamp or datetime.now(timezone.utc).isoformat(),
        }

        # Persist to ring buffer
        buf = self._buffer(agent_type)
        buf.append(step)

        # Fan-out to all live subscriber queues (non-blocking)
        for q in self._subscriber_queues(agent_type):
            q.put_nowait(step)

    async def stream_steps(self, agent_type: str):
        """Async generator — yields history first, then live events.

        1. Yields all buffered steps (most recent ``max_buffer``).
        2. Creates an ``asyncio.Queue`` and waits for new events.
        3. On generator close (disconnect) removes the queue.

        Usage::

            async for step in manager.stream_steps("supervisor"):
                yield f"event: step\\ndata: {json.dumps(step)}\\n\\n"
        """
        # 1. Replay history
        for step in self.get_recent_steps(agent_type, limit=self._max_buffer):
            yield step

        # 2. Live subscription
        queue: asyncio.Queue = asyncio.Queue()
        subs = self._subscriber_queues(agent_type)
        subs.append(queue)
        try:
            while True:
                step = await queue.get()
                yield step
        finally:
            # 3. Cleanup on disconnect
            if queue in subs:
                subs.remove(queue)

    def get_recent_steps(
        self, agent_type: str, limit: int = 20,
    ) -> list[dict]:
        """Return the most recent *limit* steps for an agent type.

        Returns an empty list when no steps exist for *agent_type*.
        """
        buf = self._buffers.get(agent_type, deque())
        return list(buf)[-limit:]
