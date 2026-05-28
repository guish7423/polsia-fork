"""Dashboard API routes — aggregated status overview."""

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import verify_api_key
from app.core.database import get_db
from app.models.activity_log import ActivityLog
from app.models.company_config import CompanyConfig
from app.models.report import DailyReport
from app.services.report_service import compute_dashboard_summary

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/summary")
async def get_dashboard_summary(
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Get aggregated dashboard summary from all services."""
    summary = await compute_dashboard_summary(db)

    # Include KPIs from company config
    company = (await db.execute(select(CompanyConfig).limit(1))).scalar_one_or_none()
    if company and company.kpis:
        summary["kpis"] = company.kpis

    return summary


@router.get("/dashboard/activity")
async def get_dashboard_activity(
    limit: int = 50,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Get recent activity entries."""
    result = await db.execute(
        select(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(limit)
    )
    return [
        {
            "id": e.id,
            "agent_type": e.agent_type,
            "action": e.action,
            "summary": e.summary,
            "level": e.level,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in result.scalars().all()
    ]


@router.get("/dashboard/reports/daily")
async def get_daily_report(
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Get the most recent daily report."""
    result = await db.execute(
        select(DailyReport).order_by(DailyReport.report_date.desc()).limit(1)
    )
    report = result.scalar_one_or_none()
    if not report:
        return None
    return {
        "id": report.id,
        "report_date": report.report_date.isoformat() if report.report_date else None,
        "morning_plan": report.morning_plan,
        "evening_summary": report.evening_summary,
        "tasks_planned": report.tasks_planned,
        "tasks_completed": report.tasks_completed,
        "tasks_failed": report.tasks_failed,
    }
