"""Memory service — dual writes to ChromaDB + PostgreSQL."""

import uuid

from app.core.chroma_client import get_collection

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

    # Write to ChromaDB for vector search
    collection = get_collection()
    collection.add(
        ids=[chroma_id],
        documents=[content],
        metadatas=[{"title": title, "category": category, "source": source or ""}],
    )

    return entry


async def list_memories(
    db: AsyncSession,
    category: str | None = None,
    limit: int = 50,
) -> list[MemoryEntry]:
    """List memory entries with optional category filter."""
    result = await db.execute(
        select(MemoryEntry)
        .order_by(MemoryEntry.created_at.desc())
        .limit(limit)
    )
    entries = list(result.scalars().all())
    if category:
        entries = [e for e in entries if e.category == category]
    return entries


async def search_memory(
    db: AsyncSession,
    query_str: str = "",
    n_results: int = 5,
    category: str | None = None,
) -> list[dict]:
    """Search memory entries — hybrid DB + ChromaDB search.

    Returns list of dicts with content/metadata for backward compat.
    When query_str is empty, returns recent entries (DB-only).
    """
    # Try ChromaDB search first when query_str is provided
    # Try ChromaDB search first when query_str is provided
    if query_str:
        collection = get_collection()
        chroma_results = collection.query(
            query_texts=[query_str],
            n_results=n_results,
        )
        if chroma_results and chroma_results.get("documents") and chroma_results["documents"][0]:
            return [
                {
                    "content": chroma_results["documents"][0][i],
                    "title": (chroma_results.get("metadatas") or [{}])[0][i].get("title", "") if chroma_results.get("metadatas") and chroma_results["metadatas"][0] else "",
                    "category": (chroma_results.get("metadatas") or [{}])[0][i].get("category", "") if chroma_results.get("metadatas") and chroma_results["metadatas"][0] else "",
                    "chroma_id": chroma_results["ids"][0][i] if chroma_results.get("ids") else "",
                }
                for i in range(len(chroma_results["documents"][0]))
            ]

    # DB search fallback
    query = select(MemoryEntry).order_by(MemoryEntry.created_at.desc()).limit(n_results)
    if category:
        query = query.where(MemoryEntry.category == category)
    result = await db.execute(query)
    entries = list(result.scalars().all())

    # Basic keyword filter if query_str provided
    if query_str:
        q = query_str.lower()
        entries = [
            e for e in entries
            if q in (e.content or "").lower() or q in (e.title or "").lower()
        ]

    # Return dict format for search results (test expects list[dict])
    return [
        {
            "content": e.content,
            "title": e.title,
            "category": e.category,
            "id": e.id,
            "chroma_id": e.chroma_id,
        }
        for e in entries
    ]


async def get_memory_by_chroma_id(
    db: AsyncSession, chroma_id: str
) -> MemoryEntry | None:
    """Get a memory entry by its ChromaDB ID."""
    result = await db.execute(
        select(MemoryEntry).where(MemoryEntry.chroma_id == chroma_id)
    )
    return result.scalar_one_or_none()
