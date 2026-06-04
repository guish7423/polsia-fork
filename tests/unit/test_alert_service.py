"""Test AlertService — create, resolve, query, and auto-resolve."""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.alert import Alert
from app.services.alert_service import AlertService


@pytest.mark.asyncio
async def test_create_alert(async_db_session):
    """Should create an alert with all fields."""
    alert = await AlertService.create_alert(
        async_db_session,
        tenant_id=1,
        alert_type="agent_error",
        severity="high",
        message="Agent GPT-4 crashed",
        source="agent",
        metadata_json={"agent_name": "GPT-4", "error_code": "OOM"},
    )
    assert alert.id is not None
    assert alert.tenant_id == 1
    assert alert.alert_type == "agent_error"
    assert alert.severity == "high"
    assert alert.message == "Agent GPT-4 crashed"
    assert alert.source == "agent"
    assert alert.status == "pending"
    assert alert.metadata_json == {"agent_name": "GPT-4", "error_code": "OOM"}
    assert alert.created_at is not None
    assert alert.resolved_at is None


@pytest.mark.asyncio
async def test_resolve_alert(async_db_session):
    """Should set status to resolved and record resolved_at."""
    alert = await AlertService.create_alert(
        async_db_session,
        tenant_id=1,
        alert_type="system",
        severity="low",
        message="Disk 80%",
        source="system",
    )
    resolved = await AlertService.resolve_alert(async_db_session, alert.id)
    assert resolved is not None
    assert resolved.status == "resolved"
    assert resolved.resolved_at is not None


@pytest.mark.asyncio
async def test_get_active_alerts(async_db_session):
    """Should return only pending alerts for a tenant."""
    await AlertService.create_alert(
        async_db_session, tenant_id=1, alert_type="agent_error",
        severity="high", message="A1", source="agent",
    )
    await AlertService.create_alert(
        async_db_session, tenant_id=2, alert_type="agent_error",
        severity="medium", message="A2 (other tenant)", source="agent",
    )
    a3 = await AlertService.create_alert(
        async_db_session, tenant_id=1, alert_type="system",
        severity="low", message="A3", source="system",
    )
    # Resolve one
    await AlertService.resolve_alert(async_db_session, a3.id)

    active = await AlertService.get_active_alerts(async_db_session, tenant_id=1)
    assert len(active) == 1
    assert active[0].message == "A1"


@pytest.mark.asyncio
async def test_get_alert_history(async_db_session):
    """Should return all alerts for a tenant ordered by newest first."""
    await AlertService.create_alert(
        async_db_session, tenant_id=1, alert_type="agent_error",
        severity="high", message="A", source="agent",
    )
    await AlertService.create_alert(
        async_db_session, tenant_id=1, alert_type="system",
        severity="low", message="B", source="system",
    )
    history = await AlertService.get_alert_history(async_db_session, tenant_id=1, limit=10)
    assert len(history) == 2
    messages = {a.message for a in history}
    assert messages == {"A", "B"}


@pytest.mark.asyncio
async def test_auto_resolve_old(async_db_session):
    """Should resolve alerts older than the given threshold."""
    old = await AlertService.create_alert(
        async_db_session, tenant_id=1, alert_type="agent_error",
        severity="medium", message="Old alert", source="agent",
    )
    fresh = await AlertService.create_alert(
        async_db_session, tenant_id=1, alert_type="agent_error",
        severity="medium", message="Fresh alert", source="agent",
    )
    # Manually back-date the old alert's created_at
    old_ts = datetime.now(timezone.utc) - timedelta(days=8)
    old.created_at = old_ts

    count = await AlertService.auto_resolve_old(
        async_db_session, days=7, tenant_id=1,
    )
    assert count == 1

    # Verify old is resolved, fresh is still pending
    await async_db_session.refresh(old)
    await async_db_session.refresh(fresh)
    assert old.status == "resolved"
    assert fresh.status == "pending"
