"""Daily report and dashboard summary service."""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import DailyReport
from app.models.task import Task
from app.models.activity_log import ActivityLog
from app.models.finance import RevenueSnapshot, ExpenseRecord


async def get_or_create_report(
    db: AsyncSession, report_date: date
) -> DailyReport:
    """Get existing daily report or create a new one."""
    result = await db.execute(
        select(DailyReport).where(DailyReport.report_date == report_date)
    )
    report = result.scalar_one_or_none()
    if report:
        return report

    report = DailyReport(report_date=report_date)
    db.add(report)
    await db.flush()
    return report


async def update_morning_plan(
    db: AsyncSession, report_date: date, plan: str
) -> DailyReport | None:
    """Update morning planning content."""
    report = await get_or_create_report(db, report_date)
    report.morning_plan = plan
    await db.flush()
    return report


async def update_evening_summary(
    db: AsyncSession, report_date: date, summary: str,
    tasks_planned: int = 0, tasks_completed: int = 0, tasks_failed: int = 0,
) -> DailyReport | None:
    """Update evening summary with task counts."""
    report = await get_or_create_report(db, report_date)
    report.evening_summary = summary
    report.tasks_planned = tasks_planned
    report.tasks_completed = tasks_completed
    report.tasks_failed = tasks_failed
    await db.flush()
    return report


async def compute_dashboard_summary(db: AsyncSession) -> dict:
    """Compute aggregated dashboard summary for the DashboardSummary API type."""
    # Task counts
    total_tasks = (
        await db.execute(select(func.count()).select_from(Task))
    ).scalar() or 0

    pending_tasks = (
        await db.execute(
            select(func.count()).select_from(Task).where(Task.status == "pending")
        )
    ).scalar() or 0

    completed_tasks = (
        await db.execute(
            select(func.count()).select_from(Task).where(Task.status == "completed")
        )
    ).scalar() or 0

    failed_tasks = (
        await db.execute(
            select(func.count()).select_from(Task).where(Task.status == "failed")
        )
    ).scalar() or 0

    # Activity
    recent_activity_count = (
        await db.execute(
            select(func.count()).select_from(ActivityLog)
        )
    ).scalar() or 0

    # Finance
    latest_revenue = (
        await db.execute(
            select(RevenueSnapshot).order_by(RevenueSnapshot.snapshot_date.desc()).limit(1)
        )
    ).scalar_one_or_none()

    total_expenses = (
        await db.execute(
            select(func.coalesce(func.sum(ExpenseRecord.amount_cents), 0))
        )
    ).scalar() or 0

    return {
        "tasks_today_total": total_tasks,
        "tasks_today_pending": pending_tasks,
        "tasks_today_completed": completed_tasks,
        "tasks_today_failed": failed_tasks,
        "active_agents": 10,
        "recent_activity_count": recent_activity_count,
        "total_expenses_cents": total_expenses,
        "mrr_cents": latest_revenue.mrr_cents if latest_revenue else 0,
        "arr_cents": latest_revenue.arr_cents if latest_revenue else 0,
        "active_subscribers": latest_revenue.active_subscribers if latest_revenue else 0,
    }
