"""Test task_service — CRUD and state machine."""
import pytest

from app.services.tenant_service import create_tenant


async def _make_tenant(async_db_session):
    """Create a test tenant and return its id."""
    t = await create_tenant(async_db_session, name="TestCo", api_key="key_test")
    await async_db_session.flush()
    return t.id


from app.services.task_service import (
    create_task,
    get_task,
    get_tasks,
    update_task_status,
    validate_agent_type,
)


@pytest.mark.asyncio
async def test_create_task(async_db_session):
    tid = await _make_tenant(async_db_session)
    task = await create_task(
        async_db_session,
        title="Write a blog post",
        agent_type="social_media",
        priority=2,
        tenant_id=tid,
    )
    await async_db_session.commit()

    assert task.id is not None
    assert task.title == "Write a blog post"
    assert task.status == "pending"
    assert task.priority == 2


@pytest.mark.asyncio
async def test_get_task(async_db_session):
    tid = await _make_tenant(async_db_session)
    task = await create_task(async_db_session, title="Find prospects", agent_type="email_outreach", tenant_id=tid)
    await async_db_session.commit()

    fetched = await get_task(async_db_session, task.id)
    assert fetched is not None
    assert fetched.id == task.id


@pytest.mark.asyncio
async def test_get_task_not_found(async_db_session):
    result = await get_task(async_db_session, task_id=99999)
    assert result is None


@pytest.mark.asyncio
async def test_update_task_status(async_db_session):
    tid = await _make_tenant(async_db_session)
    task = await create_task(async_db_session, title="Test", agent_type="finance", tenant_id=tid)
    await async_db_session.commit()

    # 必须走合法路径: pending → in_progress → completed
    updated = await update_task_status(
        async_db_session, task.id, "in_progress"
    )
    await async_db_session.commit()
    assert updated is not None
    assert updated.status == "in_progress"

    updated = await update_task_status(
        async_db_session, task.id, "completed", result_summary="Done"
    )
    await async_db_session.commit()

    assert updated is not None
    assert updated.status == "completed"
    assert updated.result_summary == "Done"


@pytest.mark.asyncio
async def test_update_task_status_blocks_illegal(async_db_session):
    """非法转换 (pending → completed) 应抛 ValueError。"""
    import pytest as _pytest
    from app.core.status_machine import transition_status, TaskStatus

    with _pytest.raises(ValueError, match="Illegal transition"):
        transition_status(TaskStatus.PENDING, TaskStatus.COMPLETED)


@pytest.mark.asyncio
async def test_get_tasks_filters_by_status(async_db_session):
    tid = await _make_tenant(async_db_session)
    await create_task(async_db_session, title="Task A", agent_type="finance", tenant_id=tid)
    t2 = await create_task(async_db_session, title="Task B", agent_type="social_media", tenant_id=tid)
    await async_db_session.commit()
    # 合法路径
    await update_task_status(async_db_session, t2.id, "in_progress")
    await update_task_status(async_db_session, t2.id, "completed")
    await async_db_session.commit()

    pending = await get_tasks(async_db_session, status="pending")
    completed = await get_tasks(async_db_session, status="completed")

    assert all(t.status == "pending" for t in pending)
    assert all(t.status == "completed" for t in completed)


def test_validate_agent_type_valid():
    assert validate_agent_type("social_media") is True
    assert validate_agent_type("finance") is True


def test_validate_agent_type_invalid():
    assert validate_agent_type("nonexistent") is False
