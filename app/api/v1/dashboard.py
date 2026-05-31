"""Dashboard API routes — aggregated status overview."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.report_service import compute_dashboard_summary

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/summary")
async def get_dashboard_summary(db: AsyncSession = Depends(get_db)):
    """Get aggregated dashboard summary from all services."""
    summary = await compute_dashboard_summary(db)
    return summary
