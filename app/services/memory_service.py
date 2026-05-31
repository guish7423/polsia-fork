"""Memory service — dual writes to ChromaDB + PostgreSQL."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory_entry import MemoryEntry


async def store_memory(
    db: AsyncSession,
    category: str,
    title: str,
    content: str,
    source: str | None = None,
    tags: list[str] | None = None,
) -> MemoryEntry:
    """Store a memory entry in PostgreSQL (ChromaDB integration TBD)."""
    chroma_id = str(uuid.uuid4())
    entry = MemoryEntry(
        category=category,
        title=title,
        content=content,
        source=source,
        tags=tags or [],
        chroma_id=chroma_id,
    )
    db.add(entry)
    await db.flush()

    # TODO: also write to ChromaDB when vector search is needed
    # from app.core.chroma_client import get_chroma_collection
    # collection = await get_chroma_collection()
    # collection.add(ids=[chroma_id], documents=[content], metadatas=[{"title": title, "category": category}])

    return entry


async def search_memory(
    db: AsyncSession,
    category: str | None = None,
    limit: int = 20,
) -> list[MemoryEntry]:
    """Search memory entries — currently DB-only (ChromaDB vector search TBD)."""
    query = select(MemoryEntry).order_by(MemoryEntry.created_at.desc()).limit(limit)
    if category:
        query = query.where(MemoryEntry.category == category)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_memory_by_chroma_id(
    db: AsyncSession, chroma_id: str
) -> MemoryEntry | None:
    """Get a memory entry by its ChromaDB ID."""
    result = await db.execute(
        select(MemoryEntry).where(MemoryEntry.chroma_id == chroma_id)
    )
    return result.scalar_one_or_none()
