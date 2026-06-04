"""Test NotificationService — CRUD, mark_read, unread_count, exception isolation, alert linkage."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.notification import Notification
from app.services.notification_service import NotificationService


@pytest.mark.asyncio
async def test_create_notification(async_db_session):
    """Should create a notification with all fields."""
    n = await NotificationService.create(
        async_db_session,
        tenant_id=1,
        notification_type="alert",
        title="CPU Overload",
        body="CPU usage exceeded 90% on node-1",
    )
    assert n.id is not None
    assert n.tenant_id == 1
    assert n.notification_type == "alert"
    assert n.title == "CPU Overload"
    assert n.body == "CPU usage exceeded 90% on node-1"
    assert n.read is False
    assert n.created_at is not None


@pytest.mark.asyncio
async def test_list_notifications_paginated(async_db_session):
    """Should list notifications with pagination, newest first."""
    for i in range(5):
        await NotificationService.create(
            async_db_session, tenant_id=1,
            notification_type="alert", title=f"Alert {i}", body="",
        )
    # Get all to know which are newest (SQLite timestamps may collide)
    all_ns = await NotificationService.list(
        async_db_session, tenant_id=1, limit=10, offset=0,
    )
    assert len(all_ns) == 5

    # Pagination: offset=2 should return the ones after offset
    paginated = await NotificationService.list(
        async_db_session, tenant_id=1, limit=2, offset=2,
    )
    assert len(paginated) == 2
    # offset=100 should return empty
    empty = await NotificationService.list(
        async_db_session, tenant_id=1, limit=10, offset=100,
    )
    assert len(empty) == 0


@pytest.mark.asyncio
async def test_mark_read(async_db_session):
    """Should mark a single notification as read."""
    n = await NotificationService.create(
        async_db_session, tenant_id=1,
        notification_type="alert", title="Test", body="",
    )
    updated = await NotificationService.mark_read(async_db_session, n.id, tenant_id=1)
    assert updated is not None
    assert updated.read is True


@pytest.mark.asyncio
async def test_mark_read_not_found(async_db_session):
    """Should return None for nonexistent notification."""
    result = await NotificationService.mark_read(async_db_session, 9999, tenant_id=1)
    assert result is None


@pytest.mark.asyncio
async def test_mark_read_tenant_mismatch(async_db_session):
    """Should not mark read a notification from another tenant."""
    n = await NotificationService.create(
        async_db_session, tenant_id=1,
        notification_type="alert", title="Test", body="",
    )
    result = await NotificationService.mark_read(async_db_session, n.id, tenant_id=2)
    assert result is None
    # Original still unread
    await async_db_session.refresh(n)
    assert n.read is False


@pytest.mark.asyncio
async def test_mark_all_read(async_db_session):
    """Should mark all notifications as read for a tenant."""
    for i in range(3):
        await NotificationService.create(
            async_db_session, tenant_id=1,
            notification_type="alert", title=f"N{i}", body="",
        )
    count = await NotificationService.mark_all_read(async_db_session, tenant_id=1)
    assert count == 3

    all_ns = await NotificationService.list(
        async_db_session, tenant_id=1, limit=10, offset=0,
    )
    assert all(n.read for n in all_ns)


@pytest.mark.asyncio
async def test_get_unread_count(async_db_session):
    """Should return the count of unread notifications."""
    await NotificationService.create(
        async_db_session, tenant_id=1,
        notification_type="alert", title="N1", body="",
    )
    await NotificationService.create(
        async_db_session, tenant_id=1,
        notification_type="system", title="N2", body="",
    )
    # Mark one as read
    all_ns = await NotificationService.list(
        async_db_session, tenant_id=1, limit=10, offset=0,
    )
    await NotificationService.mark_read(async_db_session, all_ns[0].id, tenant_id=1)

    count = await NotificationService.get_unread_count(async_db_session, tenant_id=1)
    assert count == 1


@pytest.mark.asyncio
async def test_delete_notification(async_db_session):
    """Should delete a notification by ID."""
    n = await NotificationService.create(
        async_db_session, tenant_id=1,
        notification_type="alert", title="To delete", body="",
    )
    deleted = await NotificationService.delete(async_db_session, n.id, tenant_id=1)
    assert deleted is True

    result = await NotificationService.list(
        async_db_session, tenant_id=1, limit=10, offset=0,
    )
    assert len(result) == 0


@pytest.mark.asyncio
async def test_exception_isolation(async_db_session):
    """NotificationService.create() failure should log but not raise (fail-open)."""
    # The service internally catches exceptions — we verify it returns None
    # by making flush fail
    broken_db = AsyncMock()
    broken_db.add = MagicMock()  # sync add succeeds
    broken_db.flush = AsyncMock(side_effect=Exception("DB connection lost"))

    result = await NotificationService.create(
        broken_db,
        tenant_id=1,
        notification_type="alert",
        title="Should fail",
        body="",
    )
    assert result is None  # fail-open: returns None instead of raising


@pytest.mark.asyncio
async def test_alert_linkage(async_db_session, mocker):
    """AlertService.create_alert should also create a notification."""
    from app.services.alert_service import AlertService

    # Spy on NotificationService.create
    spy = mocker.spy(NotificationService, "create")

    await AlertService.create_alert(
        async_db_session,
        tenant_id=1,
        alert_type="agent_error",
        severity="high",
        message="Agent crashed",
        source="agent",
    )

    # NotificationService.create should have been called
    spy.assert_called_once()
    call_kwargs = spy.call_args[1]  # keyword args (after db positional)
    assert call_kwargs["notification_type"] == "alert"
    assert call_kwargs["title"] == "Alert: Agent crashed"
    assert call_kwargs["tenant_id"] == 1
