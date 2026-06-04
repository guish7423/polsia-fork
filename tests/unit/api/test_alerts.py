"""Test GET/POST /api/v1/alerts endpoints."""

import pytest

from app.models.alert import Alert
from app.services.alert_service import AlertService


@pytest.mark.asyncio
async def test_get_active_alerts_empty(api_client, auth_headers):
    """Should return empty list when no active alerts."""
    resp = await api_client.get("/api/v1/alerts/active", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"alerts": [], "total": 0}


@pytest.mark.asyncio
async def test_get_active_alerts(api_client, auth_headers, async_db_session):
    """Should return only pending alerts."""
    await AlertService.create_alert(
        async_db_session, tenant_id=0, alert_type="agent_error",
        severity="high", message="Agent crashed", source="agent",
    )
    resp = await api_client.get("/api/v1/alerts/active", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["alerts"][0]["message"] == "Agent crashed"
    assert data["alerts"][0]["status"] == "pending"


@pytest.mark.asyncio
async def test_get_alert_history(api_client, auth_headers, async_db_session):
    """Should return all alerts for the tenant."""
    await AlertService.create_alert(
        async_db_session, tenant_id=0, alert_type="agent_error",
        severity="high", message="Active alert", source="agent",
    )
    await AlertService.create_alert(
        async_db_session, tenant_id=0, alert_type="system",
        severity="low", message="Another alert", source="system",
    )
    resp = await api_client.get("/api/v1/alerts/history", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["alerts"]) == 2


@pytest.mark.asyncio
async def test_resolve_alert(api_client, auth_headers, async_db_session):
    """Should resolve an alert by ID."""
    alert = await AlertService.create_alert(
        async_db_session, tenant_id=0, alert_type="agent_error",
        severity="high", message="To resolve", source="agent",
    )
    resp = await api_client.post(
        f"/api/v1/alerts/{alert.id}/resolve",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "resolved"
    assert data["resolved_at"] is not None
