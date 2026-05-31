"""Redis pub/sub event bus for real-time activity streaming."""

import json

from app.core.redis_client import get_redis

ACTIVITY_CHANNEL = "activity:events"


async def publish_activity(
    agent_type: str, action: str, summary: str, level: str = "info"
):
    """Publish an activity event to Redis pub/sub."""
    redis = await get_redis()
    await redis.publish(
        ACTIVITY_CHANNEL,
        json.dumps(
            {
                "agent_type": agent_type,
                "action": action,
                "summary": summary,
                "level": level,
            }
        ),
    )
