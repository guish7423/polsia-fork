"""Test GET/POST /api/v1/notifications endpoints."""

import pytest

from app.services.notification_service import NotificationService


@pytest.mark.asyncio
async def test_list_notifications_empty(api_client, auth_headers):
    """Should return empty list when no notifications."""
    resp = await api_client.get("/api/v1/notifications", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["notifications"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_notifications(api_client, auth_headers, async_db_session):
    """Should return paginated notifications."""
    await NotificationService.create(
        async_db_session, tenant_id=0,
        notification_type="alert", title="Test Alert", body="Something happened",
    )
    resp = await api_client.get("/api/v1/notifications", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["notifications"][0]["title"] == "Test Alert"
    assert data["notifications"][0]["read"] is False


@pytest.mark.asyncio
async def test_get_unread_count(api_client, auth_headers, async_db_session):
    """Should return unread count."""
    await NotificationService.create(
        async_db_session, tenant_id=0,
        notification_type="alert", title="N1", body="",
    )
    await NotificationService.create(
        async_db_session, tenant_id=0,
        notification_type="system", title="N2", body="",
    )
    resp = await api_client.get(
        "/api/v1/notifications/unread-count", headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {"unread_count": 2}


@pytest.mark.asyncio
async def test_mark_read(api_client, auth_headers, async_db_session):
    """Should mark a notification as read."""
    n = await NotificationService.create(
        async_db_session, tenant_id=0,
        notification_type="alert", title="To read", body="",
    )
    resp = await api_client.post(
        f"/api/v1/notifications/{n.id}/read", headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["read"] is True


@pytest.mark.asyncio
async def test_mark_all_read(api_client, auth_headers, async_db_session):
    """Should mark all notifications as read."""
    for i in range(3):
        await NotificationService.create(
            async_db_session, tenant_id=0,
            notification_type="alert", title=f"N{i}", body="",
        )
    resp = await api_client.post(
        "/api/v1/notifications/read-all", headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["marked"] == 3
