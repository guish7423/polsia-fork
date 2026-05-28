"""Activity log service — dual writes to DB + Redis pub/sub."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import publish_activity
from app.models.activity_log import ActivityLog


async def log_activity(
    db: AsyncSession,
    agent_type: str,
    action: str,
    summary: str,
    level: str = "info",
    detail: dict | None = None,
) -> ActivityLog:
    """Log activity to DB and publish to Redis pub/sub."""
    entry = ActivityLog(
        agent_type=agent_type,
        action=action,
        summary=summary,
        level=level,
        detail=detail,
    )
    db.add(entry)
    await db.flush()

    # Also publish to Redis for real-time WebSocket delivery
    await publish_activity(agent_type, action, summary, level)

    return entry


async def get_recent_activities(
    db: AsyncSession, limit: int = 50
) -> list[ActivityLog]:
    """Get recent activity log entries (for WebSocket catch-up)."""
    result = await db.execute(
        select(ActivityLog)
        .order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc())
        .limit(limit)
    )
    return list(result.scalars().all())



async def get_recent_activity(
    db: AsyncSession, limit: int = 50
) -> list[ActivityLog]:
    """Alias for get_recent_activities. Get recent activity log entries."""
    return await get_recent_activities(db, limit)