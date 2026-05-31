"""Finance API routes — revenue and expense summary."""

from sqlalchemy import func, select
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.finance import RevenueSnapshot, ExpenseRecord

router = APIRouter(tags=["finance"])


@router.get("/finance/summary")
async def get_finance_summary(db: AsyncSession = Depends(get_db)):
    """Get finance summary with latest snapshot and expense totals."""
    latest = (
        await db.execute(
            select(RevenueSnapshot)
            .order_by(RevenueSnapshot.snapshot_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    total_expenses = (
        await db.execute(
            select(func.coalesce(func.sum(ExpenseRecord.amount_cents), 0))
        )
    ).scalar() or 0

    if latest:
        return {
            "mrr_cents": latest.mrr_cents,
            "arr_cents": latest.arr_cents,
            "total_expenses_cents": total_expenses,
            "total_revenue_cents": latest.total_revenue_month_cents,
            "active_subscribers": latest.active_subscribers,
            "snapshot_date": latest.snapshot_date.isoformat(),
        }
    return {
        "mrr_cents": 0,
        "arr_cents": 0,
        "total_expenses_cents": total_expenses,
        "total_revenue_cents": 0,
        "active_subscribers": 0,
        "snapshot_date": None,
    }
