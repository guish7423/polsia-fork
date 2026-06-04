"""Test AlertService trigger methods — from_agent_error, from_quota_warning,
from_task_failure, from_cost_anomaly — plus dedup and circuit breaker."""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.alert import Alert
from app.services.alert_service import AlertService


@pytest.mark.asyncio
async def test_from_agent_error_creates_critical_alert(async_db_session):
    """from_agent_error should create a critical alert."""
    alert = await AlertService.from_agent_error(
        async_db_session,
        tenant_id=1,
        source="agent:gpt4",
        error_count=5,
        message="Agent GPT-4 failed 5 times",
    )
    assert alert is not None
    assert alert.id is not None
    assert alert.alert_type == "agent_error"
    assert alert.severity == "critical"
    assert alert.message == "Agent GPT-4 failed 5 times"
    assert alert.source == "agent:gpt4"
    assert alert.status == "pending"

    # Verify it's persisted
    fetched = await async_db_session.get(Alert, alert.id)
    assert fetched is not None


@pytest.mark.asyncio
async def test_from_quota_warning_creates_warning_alert(async_db_session):
    """from_quota_warning should create a warning alert."""
    alert = await AlertService.from_quota_warning(
        async_db_session,
        tenant_id=1,
        source="quota:cost",
        usage_pct=92.5,
    )
    assert alert is not None
    assert alert.alert_type == "quota_warning"
    assert alert.severity == "warning"
    assert "92.5%" in alert.message
    assert alert.source == "quota:cost"


@pytest.mark.asyncio
async def test_from_task_failure_creates_warning_alert(async_db_session):
    """from_task_failure should create a warning alert."""
    alert = await AlertService.from_task_failure(
        async_db_session,
        tenant_id=1,
        source="orchestrator",
        fail_count=10,
    )
    assert alert is not None
    assert alert.alert_type == "task_failure"
    assert alert.severity == "warning"
    assert "10" in alert.message
    assert alert.source == "orchestrator"


@pytest.mark.asyncio
async def test_from_cost_anomaly_creates_info_alert(async_db_session):
    """from_cost_anomaly should create an info alert."""
    alert = await AlertService.from_cost_anomaly(
        async_db_session,
        tenant_id=1,
        source="cost_analyzer",
        increase_pct=65.0,
    )
    assert alert is not None
    assert alert.alert_type == "cost_anomaly"
    assert alert.severity == "info"
    assert "65.0%" in alert.message


@pytest.mark.asyncio
async def test_dedup_same_source_type_within_window(async_db_session):
    """Same source + same alert_type within 1h should skip duplicate."""
    # First call — should create
    first = await AlertService.from_agent_error(
        async_db_session,
        tenant_id=1,
        source="agent:gpt4",
        error_count=3,
    )
    assert first is not None

    # Second call — same source, same type, within 1h → should be deduped
    second = await AlertService.from_agent_error(
        async_db_session,
        tenant_id=1,
        source="agent:gpt4",
        error_count=5,  # Different count, but same source+type
    )
    assert second is None, "Duplicate should be skipped"

    # Verify only one alert exists
    from sqlalchemy import select, func
    query = select(func.count()).select_from(Alert).where(
        Alert.tenant_id == 1,
        Alert.alert_type == "agent_error",
    )
    count = (await async_db_session.execute(query)).scalar() or 0
    assert count == 1


@pytest.mark.asyncio
async def test_cross_type_no_dedup(async_db_session):
    """Different alert_type should not be affected by dedup."""
    # Create an agent_error alert
    await AlertService.from_agent_error(
        async_db_session,
        tenant_id=1,
        source="agent:gpt4",
        error_count=3,
    )

    # Different type, same source — should NOT be deduped
    quota_alert = await AlertService.from_quota_warning(
        async_db_session,
        tenant_id=1,
        source="agent:gpt4",
        usage_pct=95.0,
    )
    assert quota_alert is not None, "Cross-type should not dedup"
    assert quota_alert.alert_type == "quota_warning"
