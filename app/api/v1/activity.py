"""Activity log REST endpoints — historical activity feed."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.activity_service import get_recent_activities

router = APIRouter(tags=["activity"])


@router.get("/activity")
async def list_activity(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    entries = await get_recent_activities(db, limit=limit)
    return [
        {
            "id": e.id,
            "agent_type": e.agent_type,
            "action": e.action,
            "summary": e.summary,
            "level": e.level,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in entries
    ]
