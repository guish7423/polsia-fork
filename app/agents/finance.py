"""Finance Agent — financial tracking, revenue reports, expense recording."""

import random
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BasePolsiaAgent, register_agent
from app.agents.prompts import FINANCE_SYSTEM_PROMPT
from app.models.finance import ExpenseRecord, RevenueSnapshot
from app.services.activity_service import log_activity


@register_agent
class FinanceAgent(BasePolsiaAgent):
    """Generates financial snapshots and tracks expenses."""

    agent_type = "finance"

    async def run(self, db: AsyncSession, context: dict | None = None) -> dict:
        today = date.today()
        now = datetime.now(timezone.utc)

        # Check if snapshot already exists for today
        existing = await db.execute(
            select(RevenueSnapshot).where(RevenueSnapshot.snapshot_date == today)
        )
        if existing.scalar_one_or_none():
            return {"result": "snapshot_exists", "date": today.isoformat()}

        # Get previous snapshot for trend
        prev = (
            await db.execute(
                select(RevenueSnapshot)
                .order_by(RevenueSnapshot.snapshot_date.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        # Generate mock financial data
        base_mrr = prev.mrr_cents if prev else 500000  # $5,000.00
        base_subs = prev.active_subscribers if prev else 50

        mrr = int(base_mrr * (1 + random.uniform(-0.05, 0.15)))
        arr = mrr * 12
        subscribers = base_subs + random.randint(-2, 5)
        churned = max(0, random.randint(0, 3))
        new_subs = max(0, subscribers - base_subs + churned)

        snapshot = RevenueSnapshot(
            snapshot_date=today,
            mrr_cents=mrr,
            arr_cents=arr,
            active_subscribers=max(0, subscribers),
            churned_today=churned,
            new_today=new_subs,
            total_revenue_month_cents=mrr,
            stripe_balance_cents=int(mrr * 0.8),
        )
        db.add(snapshot)

        # Create a mock expense
        expense = ExpenseRecord(
            category="infrastructure",
            vendor="CloudHost Inc.",
            amount_cents=random.randint(5000, 50000),
            date=today,
            description=f"Monthly infrastructure costs ({today.strftime('%B %Y')})",
        )
        db.add(expense)

        await db.flush()

        await log_activity(
            db, agent_type="finance", action="snapshot_created",
            summary=f"MRR: ${mrr/100:.2f}, Subs: {subscribers}",
        )

        return {
            "result": "finance_snapshot_created",
            "mrr_cents": mrr,
            "arr_cents": arr,
            "active_subscribers": subscribers,
            "expense_added": True,
        }
