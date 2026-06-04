"""Tests for tenant data isolation — each tenant must only see their own data."""

import pytest
from sqlalchemy import select

from app.models.task import Task
from app.models.agent_run import AgentRun
from app.models.model_call import ModelCall
from app.models.memory_entry import MemoryEntry
from app.models.social import SocialPost


# ─── Helpers ─────────────────────────────────────────────────────────────────

async def _create_tenant(db, name: str, api_key: str):
    from app.services.tenant_service import create_tenant
    return await create_tenant(db, name=name, api_key=api_key)


async def _create_task(db, title: str, agent_type: str = "orchestrator", tenant_id: int | None = None):
    from app.services.task_service import create_task
    return await create_task(
        db, title=title, agent_type=agent_type,
        tenant_id=tenant_id,
    )


async def _create_agent_run(db, agent_type: str = "orchestrator", tenant_id: int | None = None):
    run = AgentRun(
        agent_type=agent_type,
        status="completed",
        tenant_id=tenant_id,
    )
    db.add(run)
    await db.flush()
    return run


async def _create_model_call(db, provider: str = "openai", tenant_id: int | None = None):
    call = ModelCall(
        provider=provider,
        model="gpt-4",
        input_tokens=10,
        output_tokens=20,
        cost_usd=0.001,
        duration_ms=100,
        success=True,
        tenant_id=tenant_id,
    )
    db.add(call)
    await db.flush()
    return call


async def _create_memory(db, category: str, title: str, content: str, tenant_id: int | None = None):
    entry = MemoryEntry(
        category=category,
        title=title,
        content=content,
        tags=[],
        chroma_id=f"mock-{title}",
        tenant_id=tenant_id,
    )
    db.add(entry)
    await db.flush()
    return entry


async def _create_social_post(db, content: str, platform: str = "twitter", tenant_id: int | None = None):
    post = SocialPost(
        platform=platform,
        content=content,
        status="draft",
        tenant_id=tenant_id,
    )
    db.add(post)
    await db.flush()
    return post


# ─── Task isolation ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_task_scoped_by_tenant(async_db_session):
    """Tasks from different tenants are isolated."""
    t1 = await _create_tenant(async_db_session, name="T1", api_key="k1")
    t2 = await _create_tenant(async_db_session, name="T2", api_key="k2")
    await _create_task(async_db_session, title="T1 Task", agent_type="orch", tenant_id=t1.id)
    await _create_task(async_db_session, title="T2 Task", agent_type="orch", tenant_id=t2.id)

    from app.services.task_service import get_tasks
    tasks_t1 = await get_tasks(async_db_session, tenant_id=t1.id)
    assert len(tasks_t1) == 1
    assert tasks_t1[0].title == "T1 Task"


@pytest.mark.asyncio
async def test_task_cross_tenant_update_leak(async_db_session):
    """Prevent tenant A from modifying tenant B's task."""
    t1 = await _create_tenant(async_db_session, name="T1", api_key="k1")
    t2 = await _create_tenant(async_db_session, name="T2", api_key="k2")
    task_b = await _create_task(async_db_session, title="Secret", agent_type="orch", tenant_id=t2.id)

    from app.services.task_service import update_task_status
    result = await update_task_status(
        async_db_session, task_b.id, "running", tenant_id=t1.id
    )
    assert result is None  # should not find it


@pytest.mark.asyncio
async def test_task_count_scoped(async_db_session):
    """Task counts are per-tenant."""
    t1 = await _create_tenant(async_db_session, name="T1", api_key="k1")
    t2 = await _create_tenant(async_db_session, name="T2", api_key="k2")
    await _create_task(async_db_session, title="A", agent_type="orch", tenant_id=t1.id)
    await _create_task(async_db_session, title="B", agent_type="orch", tenant_id=t1.id)
    await _create_task(async_db_session, title="C", agent_type="orch", tenant_id=t2.id)

    from app.services.task_service import get_tasks_today
    count_t1 = await get_tasks_today(async_db_session, tenant_id=t1.id)
    count_t2 = await get_tasks_today(async_db_session, tenant_id=t2.id)
    assert count_t1 == 2
    assert count_t2 == 1


# ─── AgentRun isolation ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_agent_run_scoped(async_db_session):
    """AgentRun records are isolated by tenant."""
    t1 = await _create_tenant(async_db_session, name="T1", api_key="k1")
    t2 = await _create_tenant(async_db_session, name="T2", api_key="k2")
    await _create_agent_run(async_db_session, agent_type="orch", tenant_id=t1.id)
    await _create_agent_run(async_db_session, agent_type="orch", tenant_id=t2.id)

    from app.services.agent_monitor_service import get_agent_runs
    runs_t1, total_t1 = await get_agent_runs(async_db_session, tenant_id=t1.id)
    runs_t2, total_t2 = await get_agent_runs(async_db_session, tenant_id=t2.id)
    assert total_t1 == 1
    assert total_t2 == 1


# ─── ModelCall isolation ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_model_call_scoped(async_db_session):
    """ModelCall records are isolated by tenant."""
    t1 = await _create_tenant(async_db_session, name="T1", api_key="k1")
    t2 = await _create_tenant(async_db_session, name="T2", api_key="k2")
    await _create_model_call(async_db_session, provider="openai", tenant_id=t1.id)
    await _create_model_call(async_db_session, provider="openai", tenant_id=t2.id)

    from app.services.model_usage_service import get_usage_stats
    stats_t1 = await get_usage_stats(async_db_session, tenant_id=t1.id)
    stats_t2 = await get_usage_stats(async_db_session, tenant_id=t2.id)
    assert stats_t1["total_calls"] == 1
    assert stats_t2["total_calls"] == 1


# ─── MemoryEntry isolation ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_memory_entry_scoped(async_db_session):
    """Memory entries are isolated by tenant."""
    t1 = await _create_tenant(async_db_session, name="T1", api_key="k1")
    t2 = await _create_tenant(async_db_session, name="T2", api_key="k2")
    await _create_memory(async_db_session, "strategy", "T1 Plan", "content", tenant_id=t1.id)
    await _create_memory(async_db_session, "strategy", "T2 Plan", "content", tenant_id=t2.id)

    from app.services.memory_service import search_memory
    mems_t1 = await search_memory(async_db_session, tenant_id=t1.id)
    mems_t2 = await search_memory(async_db_session, tenant_id=t2.id)
    assert len(mems_t1) == 1
    assert mems_t1[0].title == "T1 Plan"
    assert len(mems_t2) == 1
    assert mems_t2[0].title == "T2 Plan"


# ─── SocialPost isolation ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_social_post_scoped(async_db_session):
    """Social posts are isolated by tenant."""
    t1 = await _create_tenant(async_db_session, name="T1", api_key="k1")
    t2 = await _create_tenant(async_db_session, name="T2", api_key="k2")
    await _create_social_post(async_db_session, "Post from T1", tenant_id=t1.id)
    await _create_social_post(async_db_session, "Post from T2", tenant_id=t2.id)

    result = await async_db_session.execute(
        select(SocialPost).where(SocialPost.tenant_id == t1.id)
    )
    posts = result.scalars().all()
    assert len(posts) == 1
    assert posts[0].content == "Post from T1"
