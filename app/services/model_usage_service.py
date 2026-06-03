"""Model usage analytics service — query and aggregate ModelCall data."""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model_call import ModelCall


async def record_model_call(
    db: AsyncSession,
    *,
    provider: str,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost_usd: float = 0.0,
    duration_ms: int = 0,
    success: bool = True,
    task_category: str | None = None,
    error: str | None = None,
) -> ModelCall:
    """Insert a ModelCall record and return it."""
    record = ModelCall(
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        duration_ms=duration_ms,
        success=success,
        task_category=task_category,
        error=error,
    )
    db.add(record)
    await db.flush()
    return record


async def get_usage_stats(
    db: AsyncSession,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
) -> dict:
    """Aggregate usage statistics over a time range.

    Returns total calls, tokens, cost, and success rate.
    """
    where_conditions = []
    if since is not None:
        where_conditions.append(ModelCall.created_at >= since)
    if until is not None:
        where_conditions.append(ModelCall.created_at < until)

    base = select(ModelCall)
    if where_conditions:
        base = base.where(*where_conditions)

    # Total counts
    count_q = select(func.count()).select_from(ModelCall)
    if where_conditions:
        count_q = count_q.where(*where_conditions)
    total_calls = (await db.execute(count_q)).scalar() or 0

    # Success count
    success_q = (
        select(func.count())
        .select_from(ModelCall)
        .where(ModelCall.success.is_(True))
    )
    if where_conditions:
        success_q = success_q.where(*where_conditions)
    success_calls = (await db.execute(success_q)).scalar() or 0

    # Aggregated tokens and cost
    agg_q = select(
        func.coalesce(func.sum(ModelCall.input_tokens), 0).label("total_input_tokens"),
        func.coalesce(func.sum(ModelCall.output_tokens), 0).label("total_output_tokens"),
        func.coalesce(func.sum(ModelCall.cost_usd), 0.0).label("total_cost_usd"),
        func.coalesce(func.avg(ModelCall.duration_ms), 0.0).label("avg_duration_ms"),
    )
    if where_conditions:
        agg_q = agg_q.where(*where_conditions)
    agg_row = (await db.execute(agg_q)).one()

    return {
        "total_calls": total_calls,
        "success_calls": success_calls,
        "failed_calls": total_calls - success_calls,
        "success_rate": round(success_calls / total_calls, 4) if total_calls > 0 else 0,
        "total_input_tokens": agg_row.total_input_tokens,
        "total_output_tokens": agg_row.total_output_tokens,
        "total_cost_usd": round(float(agg_row.total_cost_usd), 6),
        "avg_duration_ms": round(float(agg_row.avg_duration_ms), 1),
    }


async def get_model_breakdown(
    db: AsyncSession,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[dict]:
    """Per-model cost and token breakdown.

    Returns list of dicts with provider, model, call count, tokens, cost.
    """
    where_clause = ""
    params: dict = {}
    if since is not None:
        where_clause += " AND created_at >= :since"
        params["since"] = since
    if until is not None:
        where_clause += " AND created_at < :until"
        params["until"] = until

    sql = f"""
        SELECT
            provider,
            model,
            COUNT(*)                           AS calls,
            COALESCE(SUM(input_tokens), 0)     AS input_tokens,
            COALESCE(SUM(output_tokens), 0)    AS output_tokens,
            COALESCE(SUM(cost_usd), 0.0)       AS cost_usd,
            COALESCE(AVG(duration_ms), 0.0)    AS avg_duration_ms
        FROM model_calls
        WHERE 1=1 {where_clause}
        GROUP BY provider, model
        ORDER BY cost_usd DESC
    """
    rows = (await db.execute(text(sql), params)).all()

    return [
        {
            "provider": r.provider,
            "model": r.model,
            "calls": r.calls,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
            "cost_usd": round(float(r.cost_usd), 6),
            "avg_duration_ms": round(float(r.avg_duration_ms), 1),
        }
        for r in rows
    ]


async def get_daily_usage(
    db: AsyncSession,
    days: int = 30,
) -> list[dict]:
    """Daily usage aggregation for trend charts.

    Returns list of ``{date, calls, input_tokens, output_tokens, cost_usd}``.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    sql = """
        SELECT
            DATE(created_at)                    AS day,
            COUNT(*)                           AS calls,
            COALESCE(SUM(input_tokens), 0)     AS input_tokens,
            COALESCE(SUM(output_tokens), 0)    AS output_tokens,
            COALESCE(SUM(cost_usd), 0.0)       AS cost_usd
        FROM model_calls
        WHERE created_at >= :since
        GROUP BY DATE(created_at)
        ORDER BY day ASC
    """
    rows = (await db.execute(text(sql), {"since": since})).all()
    return [
        {
            "date": str(r.day),
            "calls": r.calls,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
            "cost_usd": round(float(r.cost_usd), 6),
        }
        for r in rows
    ]


async def get_recent_calls(
    db: AsyncSession,
    limit: int = 50,
) -> list[dict]:
    """Most recent LLM calls."""
    q = (
        select(ModelCall)
        .order_by(ModelCall.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(q)).scalars().all()
    return [
        {
            "id": r.id,
            "provider": r.provider,
            "model": r.model,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
            "cost_usd": round(r.cost_usd, 6),
            "duration_ms": r.duration_ms,
            "success": r.success,
            "task_category": r.task_category,
            "error": r.error,
            "created_at": str(r.created_at),
        }
        for r in rows
    ]


async def get_task_category_breakdown(
    db: AsyncSession,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[dict]:
    """Usage breakdown by task category."""
    where_clause = ""
    params: dict = {}
    if since is not None:
        where_clause += " AND created_at >= :since"
        params["since"] = since
    if until is not None:
        where_clause += " AND created_at < :until"
        params["until"] = until

    sql = f"""
        SELECT
            task_category,
            COUNT(*)                           AS calls,
            COALESCE(SUM(input_tokens), 0)     AS input_tokens,
            COALESCE(SUM(output_tokens), 0)    AS output_tokens,
            COALESCE(SUM(cost_usd), 0.0)       AS cost_usd
        FROM model_calls
        WHERE task_category IS NOT NULL {where_clause}
        GROUP BY task_category
        ORDER BY cost_usd DESC
    """
    rows = (await db.execute(text(sql), params)).all()
    return [
        {
            "task_category": r.task_category,
            "calls": r.calls,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
            "cost_usd": round(float(r.cost_usd), 6),
        }
        for r in rows
    ]
