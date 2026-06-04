"""Agent monitoring service — real-time status, run history, cost aggregation."""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_run import AgentRun
from app.models.model_call import ModelCall
from app.services.task_service import VALID_AGENT_TYPES

AGENT_DESCRIPTIONS: dict[str, str] = {
    "orchestrator": "Daily planning and agent coordination",
    "business_planning": "Strategic planning and KPI refinement",
    "competitor_research": "Competitive analysis and market research",
    "social_media": "Social media content creation and publishing",
    "email_outreach": "Customer prospecting and email marketing",
    "customer_support": "Automated customer inquiry responses",
    "ads_management": "Ad campaign optimization and budget allocation",
    "code_generation": "Code writing for company product",
    "finance": "Financial tracking and revenue reporting",
    "deployment": "Deployment lifecycle management",
    "deploy_agent": "Deployment planning and execution",
    "evolution": "Agent performance analysis and improvement",
    "market_intel": "Market intelligence and daily briefing",
    "order_scanner": "External platform order scanning",
    "order_fulfiller": "Order fulfillment and delivery",
    "lead_nurturing": "Lead follow-up and nurturing",
    "monitor": "Service health monitoring",
}


async def get_agent_monitor(db: AsyncSession, tenant_id: int | None = None) -> list[dict]:
    """Build a real-time agent monitor snapshot.

    For each registered agent type, returns its current status (idle/running),
    latest run info, and aggregate stats from the last 24h.
    """
    # 1️⃣ Latest run per agent type (subquery)
    latest_per_agent = (
        select(
            AgentRun.agent_type,
            func.max(AgentRun.id).label("max_id"),
        )
        .group_by(AgentRun.agent_type)
        .subquery()
    )

    latest_runs = await db.execute(
        select(AgentRun)
        .join(
            latest_per_agent,
            AgentRun.id == latest_per_agent.c.max_id,
        )
    )
    latest_map: dict[str, AgentRun] = {
        r.agent_type: r for r in latest_runs.scalars().all()
    }

    # 2️⃣ 24h aggregate stats per agent type
    since = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # Run counts and total cost from AgentRun
    run_stats_query = (
        select(
            AgentRun.agent_type,
            func.count().label("run_count"),
            func.avg(AgentRun.duration_secs).label("avg_duration"),
            func.sum(AgentRun.tokens_used).label("total_tokens"),
            func.coalesce(func.sum(AgentRun.cost_usd), 0).label("total_cost"),
        )
        .where(AgentRun.started_at >= since)
        .group_by(AgentRun.agent_type)
    )
    if tenant_id is not None:
        run_stats_query = run_stats_query.where(AgentRun.tenant_id == tenant_id)
    run_stats_raw = await db.execute(run_stats_query)
    run_stats: dict[str, dict] = {}
    for row in run_stats_raw.all():
        run_stats[row.agent_type] = {
            "run_count": row.run_count,
            "avg_duration_secs": round(float(row.avg_duration), 2) if row.avg_duration else None,
            "total_tokens": row.total_tokens or 0,
            "total_cost_usd": round(float(row.total_cost), 6),
        }

    # 3️⃣ Assemble monitor response
    monitor: list[dict] = []
    for agent_type in VALID_AGENT_TYPES:
        latest = latest_map.get(agent_type)
        stats = run_stats.get(agent_type, {})

        # Determine current status
        status = "idle"
        if latest and latest.status == "running":
            status = "running"
        elif latest and latest.status == "error":
            status = "error"

        entry = {
            "agent_type": agent_type,
            "name": agent_type.replace("_", " ").title(),
            "description": AGENT_DESCRIPTIONS.get(agent_type, ""),
            "status": status,
            "last_run": {
                "run_id": latest.id if latest else None,
                "status": latest.status if latest else None,
                "duration_secs": latest.duration_secs if latest else None,
                "cost_usd": latest.cost_usd if latest else None,
                "started_at": latest.started_at.isoformat() if latest and latest.started_at else None,
            }
            if latest
            else None,
            "today": {
                "run_count": stats.get("run_count", 0),
                "avg_duration_secs": stats.get("avg_duration_secs"),
                "total_tokens": stats.get("total_tokens", 0),
                "total_cost_usd": stats.get("total_cost_usd", 0),
            },
        }
        monitor.append(entry)

    return monitor


async def get_agent_runs(
    db: AsyncSession,
    agent_type: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    tenant_id: int | None = None,
) -> tuple[list[AgentRun], int]:
    """List agent runs with optional filters. Returns (runs, total_count)."""
    query = select(AgentRun)
    count_query = select(func.count()).select_from(AgentRun)

    if agent_type:
        query = query.where(AgentRun.agent_type == agent_type)
        count_query = count_query.where(AgentRun.agent_type == agent_type)
    if status:
        query = query.where(AgentRun.status == status)
        count_query = count_query.where(AgentRun.status == status)
    if tenant_id is not None:
        query = query.where(AgentRun.tenant_id == tenant_id)
        count_query = count_query.where(AgentRun.tenant_id == tenant_id)

    # Total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginated rows
    result = await db.execute(
        query.order_by(AgentRun.started_at.desc()).offset(offset).limit(limit)
    )
    runs = list(result.scalars().all())
    return runs, total


async def get_agent_run_detail(
    db: AsyncSession,
    run_id: int,
) -> dict | None:
    """Get detailed info for a single agent run, enriched with LLM call data."""
    run = await db.get(AgentRun, run_id)
    if not run:
        return None

    # Join ModelCall records for this run's time window
    # (match by agent_type + approximate time range)
    llm_calls_result = await db.execute(
        select(ModelCall)
        .where(ModelCall.created_at >= run.started_at)
        .where(
            ModelCall.created_at <= (run.ended_at or run.started_at)
        )
        .order_by(ModelCall.created_at)
        .limit(200)
    )
    llm_calls = list(llm_calls_result.scalars().all())

    return {
        "id": run.id,
        "task_id": run.task_id,
        "agent_type": run.agent_type,
        "run_type": run.run_type,
        "status": run.status,
        "input_context": run.input_context,
        "output": run.output,
        "telemetry": {
            "tokens_used": run.tokens_used,
            "cost_usd": run.cost_usd,
            "duration_secs": run.duration_secs,
            "llm_call_count": run.llm_call_count,
        },
        "execution_spans": run.execution_spans,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "ended_at": run.ended_at.isoformat() if run.ended_at else None,
        "llm_calls": [
            {
                "id": c.id,
                "provider": c.provider,
                "model": c.model,
                "input_tokens": c.input_tokens,
                "output_tokens": c.output_tokens,
                "cost_usd": c.cost_usd,
                "duration_ms": c.duration_ms,
                "success": c.success,
                "error": c.error,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in llm_calls
        ],
    }


async def get_agent_run_stats(
    db: AsyncSession,
    agent_type: str | None = None,
    days: int = 7,
    tenant_id: int | None = None,
) -> dict:
    """Aggregate run stats for the last N days."""
    since = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    import datetime as dt
    since -= dt.timedelta(days=days - 1)

    query = select(
        AgentRun.agent_type,
        func.date(AgentRun.started_at).label("day"),
        func.count().label("run_count"),
        func.avg(AgentRun.duration_secs).label("avg_duration"),
        func.sum(AgentRun.cost_usd).label("total_cost"),
        func.avg(AgentRun.tokens_used).label("avg_tokens"),
        func.sum(AgentRun.tokens_used).label("total_tokens"),
    ).where(AgentRun.started_at >= since)

    if agent_type:
        query = query.where(AgentRun.agent_type == agent_type)
    if tenant_id is not None:
        query = query.where(AgentRun.tenant_id == tenant_id)

    query = query.group_by(AgentRun.agent_type, func.date(AgentRun.started_at))
    query = query.order_by(AgentRun.agent_type, func.date(AgentRun.started_at))

    result = await db.execute(query)
    rows = result.all()

    # Build summary
    daily: list[dict] = []
    by_agent: dict[str, list[dict]] = {}
    for row in rows:
        entry = {
            "day": str(row.day),
            "run_count": row.run_count,
            "avg_duration_secs": round(float(row.avg_duration), 2) if row.avg_duration else None,
            "total_cost_usd": round(float(row.total_cost), 6) if row.total_cost else 0,
            "avg_tokens": round(float(row.avg_tokens), 0) if row.avg_tokens else None,
            "total_tokens": row.total_tokens or 0,
        }
        daily.append(entry)
        by_agent.setdefault(row.agent_type, []).append(entry)

    # Totals
    total_runs = sum(e["run_count"] for e in daily)
    total_cost = sum(e["total_cost_usd"] for e in daily)
    total_tokens = sum(e["total_tokens"] for e in daily)

    return {
        "days": days,
        "total_runs": total_runs,
        "total_cost_usd": round(total_cost, 6),
        "total_tokens": total_tokens,
        "daily": daily,
        "by_agent": by_agent,
    }
