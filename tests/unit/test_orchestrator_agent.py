"""Test OrchestratorAgent — daily planning."""
import pytest
from datetime import date

from app.models.report import DailyReport
from app.models.task import Task


@pytest.mark.asyncio
async def test_orchestrator_creates_tasks(async_db_session, mock_redis):
    from app.agents.orchestrator import OrchestratorAgent

    agent = OrchestratorAgent()
    result = await agent.run(async_db_session)
    await async_db_session.commit()

    assert result["result"] == "daily_plan_created"
    assert result["tasks_planned"] >= 0


@pytest.mark.asyncio
async def test_orchestrator_creates_daily_report(async_db_session, mock_redis):
    from app.agents.orchestrator import OrchestratorAgent

    agent = OrchestratorAgent()
    await agent.run(async_db_session)
    await async_db_session.commit()

    from sqlalchemy import select
    result = await async_db_session.execute(
        select(DailyReport).where(DailyReport.report_date == date.today())
    )
    report = result.scalar_one_or_none()
    assert report is not None
    assert report.morning_plan is not None
