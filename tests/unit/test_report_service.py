"""Test report_service — daily report lifecycle."""
import pytest
from datetime import date

from app.services.report_service import (
    get_or_create_report,
    update_morning_plan,
    update_evening_summary,
    compute_dashboard_summary,
)


@pytest.mark.asyncio
async def test_get_or_create_creates_new(async_db_session):
    today = date.today()
    report = await get_or_create_report(async_db_session, today)
    assert report.id is not None
    assert report.report_date == today
    assert report.morning_plan is None


@pytest.mark.asyncio
async def test_get_or_create_is_idempotent(async_db_session):
    today = date.today()
    r1 = await get_or_create_report(async_db_session, today)
    await async_db_session.commit()
    r2 = await get_or_create_report(async_db_session, today)
    assert r1.id == r2.id


@pytest.mark.asyncio
async def test_update_morning_plan(async_db_session):
    today = date.today()
    report = await update_morning_plan(async_db_session, today, "Focus on outreach")
    await async_db_session.commit()

    assert report.morning_plan == "Focus on outreach"


@pytest.mark.asyncio
async def test_update_evening_summary(async_db_session):
    today = date.today()
    report = await update_evening_summary(
        async_db_session,
        today,
        summary="Good day overall",
        tasks_planned=5,
        tasks_completed=4,
        tasks_failed=1,
    )
    await async_db_session.commit()

    assert report.evening_summary == "Good day overall"
    assert report.tasks_planned == 5
    assert report.tasks_completed == 4
    assert report.tasks_failed == 1


@pytest.mark.asyncio
async def test_compute_dashboard_summary_empty(async_db_session):
    summary = await compute_dashboard_summary(async_db_session)
    assert summary["tasks_today_total"] == 0
    assert summary["active_agents"] == 10
    assert summary["mrr_cents"] == 0
