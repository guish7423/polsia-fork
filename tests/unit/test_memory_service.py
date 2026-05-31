"""Test memory_service — PG-backed memory CRUD."""
import pytest

from app.services.memory_service import search_memory, store_memory


@pytest.mark.asyncio
async def test_store_memory_creates_pg_record(async_db_session):
    entry = await store_memory(
        async_db_session,
        category="strategy",
        title="Growth lever identified",
        content="Referral program drives 30% of sign-ups at competitors",
        source="competitor_research",
        tags=["growth", "referral"],
    )
    await async_db_session.commit()

    assert entry.id is not None
    assert entry.category == "strategy"
    assert entry.chroma_id is not None


@pytest.mark.asyncio
async def test_store_memory_generates_chroma_id(async_db_session):
    entry = await store_memory(
        async_db_session,
        category="competitor",
        title="Competitor pricing",
        content="Acme charges $99/mo for the starter plan",
    )
    assert entry.chroma_id is not None
    assert isinstance(entry.chroma_id, str)
    assert len(entry.chroma_id) > 0


@pytest.mark.asyncio
async def test_search_memory_returns_all(async_db_session):
    await store_memory(async_db_session, category="strategy", title="S1", content="Alpha plan")
    await store_memory(async_db_session, category="competitor", title="C1", content="Beta plan")
    await async_db_session.commit()

    results = await search_memory(async_db_session)
    assert isinstance(results, list)
    assert len(results) == 2


@pytest.mark.asyncio
async def test_search_memory_filters_by_category(async_db_session):
    await store_memory(async_db_session, category="strategy", title="S1", content="c1")
    await store_memory(async_db_session, category="competitor", title="C1", content="c2")
    await async_db_session.commit()

    strategy = await search_memory(async_db_session, category="strategy")
    assert all(m.category == "strategy" for m in strategy)
    assert len(strategy) == 1


@pytest.mark.asyncio
async def test_search_memory_respects_limit(async_db_session):
    for i in range(5):
        await store_memory(async_db_session, category="strategy", title=f"S{i}", content=f"c{i}")
    await async_db_session.commit()

    results = await search_memory(async_db_session, limit=3)
    assert len(results) <= 3
