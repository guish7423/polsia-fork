"""Social media posts API routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import verify_api_key
from app.core.database import get_db
from app.models.social import SocialPost

router = APIRouter(tags=["social"])


@router.get("/social/posts")
async def list_posts(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """List social media posts with optional status filter."""
    query = select(SocialPost).order_by(SocialPost.created_at.desc()).limit(limit)
    if status:
        query = query.where(SocialPost.status == status)
    result = await db.execute(query)
    return [
        {
            "id": p.id,
            "platform": p.platform,
            "content": p.content,
            "status": p.status,
            "scheduled_for": p.scheduled_for.isoformat() if p.scheduled_for else None,
            "published_at": p.published_at.isoformat() if p.published_at else None,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in result.scalars().all()
    ]
