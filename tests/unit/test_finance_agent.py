"""Test FinanceAgent — revenue snapshot generation."""
import pytest
from datetime import date

from app.models.finance import RevenueSnapshot, ExpenseRecord


@pytest.mark.asyncio
async def test_finance_agent_creates_snapshot(async_db_session, mock_redis):
    from app.agents.finance import FinanceAgent

    agent = FinanceAgent()
    result = await agent.run(async_db_session)
    await async_db_session.commit()

    assert result["result"] == "finance_snapshot_created"
    assert result["mrr_cents"] > 0

    from sqlalchemy import select
    snap = (await async_db_session.execute(
        select(RevenueSnapshot).where(RevenueSnapshot.snapshot_date == date.today())
    )).scalar_one_or_none()
    assert snap is not None
    assert snap.mrr_cents == result["mrr_cents"]


@pytest.mark.asyncio
async def test_finance_agent_skips_existing_snapshot(async_db_session, mock_redis):
    from app.agents.finance import FinanceAgent
    from app.models.finance import RevenueSnapshot

    snap = RevenueSnapshot(snapshot_date=date.today(), mrr_cents=100000, arr_cents=1200000, active_subscribers=10)
    async_db_session.add(snap)
    await async_db_session.commit()

    agent = FinanceAgent()
    result = await agent.run(async_db_session)

    assert result["result"] == "snapshot_exists"


@pytest.mark.asyncio
async def test_finance_agent_adds_expense(async_db_session, mock_redis):
    from app.agents.finance import FinanceAgent

    agent = FinanceAgent()
    result = await agent.run(async_db_session)
    await async_db_session.commit()

    assert result["expense_added"] is True

    from sqlalchemy import select, func
    count = (await async_db_session.execute(
        select(func.count()).select_from(ExpenseRecord)
    )).scalar()
    assert count > 0
