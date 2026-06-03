"""LLM usage/cost tracking API routes — powered by ModelCall table."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import verify_api_key
from app.core.database import get_db
from app.services.model_usage_service import (
    get_daily_usage,
    get_model_breakdown,
    get_recent_calls,
    get_task_category_breakdown,
    get_usage_stats,
)

router = APIRouter(prefix="/usage", tags=["usage"])


def _parse_period(period: str) -> tuple[datetime, datetime]:
    """Convert a period string to (since, until) datetimes."""
    now = datetime.now(timezone.utc)
    if period == "today":
        since = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return since, now
    elif period == "7d":
        return now - timedelta(days=7), now
    elif period == "30d":
        return now - timedelta(days=30), now
    elif period == "90d":
        return now - timedelta(days=90), now
    else:
        return now - timedelta(days=7), now


@router.get("/stats")
async def get_usage_statistics(
    period: str = Query("7d", description="Time range: today, 7d, 30d, 90d"),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Aggregated usage statistics over a time period."""
    since, until = _parse_period(period)
    stats = await get_usage_stats(db, since=since, until=until)
    model_breakdown = await get_model_breakdown(db, since=since, until=until)
    category_breakdown = await get_task_category_breakdown(db, since=since, until=until)
    daily = await get_daily_usage(db, days=30)

    return {
        "period": period,
        "summary": stats,
        "by_model": model_breakdown,
        "by_category": category_breakdown,
        "daily_trend": daily,
    }


@router.get("/recent")
async def get_recent_llm_calls(
    limit: int = Query(50, description="Number of recent calls to return"),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Most recent LLM API calls."""
    calls = await get_recent_calls(db, limit=limit)
    return {"calls": calls, "total": len(calls)}


@router.get("/costs")
async def get_llm_costs(
    period: str = Query("30d", description="Time range: today, 7d, 30d, 90d"),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Cost breakdown by model and category."""
    since, until = _parse_period(period)
    stats = await get_usage_stats(db, since=since, until=until)
    model_breakdown = await get_model_breakdown(db, since=since, until=until)

    return {
        "period": period,
        "total_cost_usd": stats["total_cost_usd"],
        "total_calls": stats["total_calls"],
        "total_input_tokens": stats["total_input_tokens"],
        "total_output_tokens": stats["total_output_tokens"],
        "by_model": model_breakdown,
    }


@router.get("/summary")
async def get_usage_summary(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """Compact usage summary for dashboard widgets.

    Returns stats for today and the last 30 days.
    """
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    today_stats = await get_usage_stats(db, since=today_start)
    month_stats = await get_usage_stats(db, since=now - timedelta(days=30))
    recent_calls = await get_recent_calls(db, limit=5)

    return {
        "today": today_stats,
        "last_30_days": month_stats,
        "recent_calls": recent_calls,
    }
