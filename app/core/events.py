"""Redis pub/sub event bus for real-time activity streaming."""

import json
from typing import Any

from app.core.redis_client import get_redis

ACTIVITY_CHANNEL = "activity:events"


async def publish_activity(
    agent_type: str,
    action: str,
    summary: str,
    level: str = "info",
    run_id: int | None = None,
    metadata: dict | None = None,
):
    """Publish an activity event to Redis pub/sub.

    Args:
        agent_type: Which agent produced this event.
        action: Event type (started, completed, error, interrupt, etc.).
        summary: Human-readable description.
        level: Severity: info, warning, error.
        run_id: Optional AgentRun ID for cross-reference.
        metadata: Optional extra payload (cost, duration, etc.).
    """
    redis = await get_redis()
    payload: dict[str, Any] = {
        "agent_type": agent_type,
        "action": action,
        "summary": summary,
        "level": level,
    }
    if run_id is not None:
        payload["run_id"] = run_id
    if metadata:
        payload["metadata"] = metadata

    await redis.publish(ACTIVITY_CHANNEL, json.dumps(payload))
