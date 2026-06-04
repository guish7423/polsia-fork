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
    tenant_id: int | None = None,
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
        tenant_id=tenant_id,
    )
    db.add(entry)
    await db.flush()

    # Also write to ChromaDB for vector search (non-blocking, fail-open)
    try:
        from app.core.chroma_client import get_collection as get_chroma_collection

        collection = get_chroma_collection()
        collection.add(
            ids=[chroma_id],
            documents=[content],
            metadatas=[{"title": title, "category": category, "tenant_id": str(tenant_id) if tenant_id else "0"}],
        )
    except Exception:
        pass

    return entry


async def search_memory(
    db: AsyncSession,
    category: str | None = None,
    limit: int = 20,
    tenant_id: int | None = None,
) -> list[MemoryEntry]:
    """Search memory entries — currently DB-only (ChromaDB vector search TBD)."""
    query = select(MemoryEntry).order_by(MemoryEntry.created_at.desc()).limit(limit)
    if category:
        query = query.where(MemoryEntry.category == category)
    if tenant_id is not None:
        query = query.where(MemoryEntry.tenant_id == tenant_id)
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


async def semantic_search_memory(
    db: AsyncSession,
    query: str,
    tenant_id: int | None = None,
    n_results: int = 5,
) -> list[MemoryEntry]:
    """Search memory entries via ChromaDB vector similarity + DB cross-ref."""
    try:
        from app.core.chroma_client import semantic_search_knowledge

        results = await semantic_search_knowledge(
            query,
            n_results=n_results,
            filter_tenant=tenant_id,
        )
    except Exception:
        return []

    if not results:
        return []

    # Cross-reference with DB to get full MemoryEntry records
    chroma_ids = [r["id"] for r in results]
    stmt = select(MemoryEntry).where(MemoryEntry.chroma_id.in_(chroma_ids))
    result = await db.execute(stmt)
    db_results = {m.chroma_id: m for m in result.scalars().all()}

    # Preserve ChromaDB ranking order
    ordered = []
    for cid in chroma_ids:
        if cid in db_results:
            ordered.append(db_results[cid])
    return ordered
