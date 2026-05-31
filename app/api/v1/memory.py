"""Memory API routes — CRUD and search for agent memories."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import verify_api_key
from app.core.database import get_db
from app.services.memory_service import search_memory, store_memory

router = APIRouter(tags=["memory"])


@router.post("/memory", status_code=201)
async def create_memory(
    body: dict,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Store a new memory entry."""
    entry = await store_memory(
        db,
        category=body.get("category", "general"),
        title=body.get("title", ""),
        content=body.get("content", ""),
        source=body.get("source"),
        tags=body.get("tags"),
    )
    return {
        "id": entry.id,
        "title": entry.title,
        "category": entry.category,
        "content": entry.content,
        "source": entry.source,
        "tags": entry.tags,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


@router.get("/memory")
async def list_or_search_memory(
    category: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """List memory entries, optionally filtered by category."""
    entries = await search_memory(db, category=category, limit=limit)
    return [
        {
            "id": e.id,
            "title": e.title,
            "category": e.category,
            "content": e.content,
            "source": e.source,
            "tags": e.tags,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in entries
    ]
