"""System Health endpoint — aggregated health check for the dashboard.

聚合 agent_monitor_service, task_service, quota_service, model_usage_service
的数据，提供一键式系统健康状态。
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import verify_api_key
from app.core.database import get_db
from app.core.tenant_context import get_current_tenant
from app.models.agent_run import AgentRun
from app.models.model_call import ModelCall
from app.models.task import Task
from app.models.tenant import Tenant
from app.services.agent_monitor_service import get_agent_monitor
from app.services.model_usage_service import get_usage_stats

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/health")
async def system_health(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_api_key),
    current_tenant=Depends(get_current_tenant),
):
    """Aggregated system health — combines agents, tasks, quotas, and costs.

    Returns ``overall`` (healthy|degraded) plus per-dimension check results.
    """
    now = datetime.now(timezone.utc)
    since_24h = now - timedelta(hours=24)
    tenant_id = current_tenant.id if current_tenant else None

    # ── 1. Agent health ────────────────────────────────────────────────────
    agents = await get_agent_monitor(db, tenant_id=tenant_id)
    errored = [a for a in agents if a["status"] == "error"]
    running = [a for a in agents if a["status"] == "running"]
    agent_status = "degraded" if errored else "healthy"

    # ── 2. Task health ─────────────────────────────────────────────────────
    total_tasks = await db.scalar(
        select(func.count()).select_from(Task)
    ) or 0

    pending = await db.scalar(
        select(func.count())
        .select_from(Task)
        .where(Task.status == "pending")
    ) or 0

    failed_24h = await db.scalar(
        select(func.count())
        .select_from(Task)
        .where(Task.status == "failed", Task.created_at >= since_24h)
    ) or 0

    task_status = "degraded" if failed_24h > 5 else "healthy"

    # ── 3. Quota health ────────────────────────────────────────────────────
    tenant_record = await db.get(Tenant, tenant_id) if tenant_id else None
    exceeded: list[str] = []
    avg_usage_pct = 0
    cost_budget_pct = 0
    quota_status = "healthy"

    if tenant_record:
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Running agents vs limit
        running_count = len(running)
        agent_limit = tenant_record.agents_limit
        agent_pct = running_count / agent_limit if agent_limit else 0

        # Monthly tasks vs limit
        tasks_this_month = await db.scalar(
            select(func.count())
            .select_from(Task)
            .where(Task.created_at >= month_start)
        ) or 0
        task_limit = tenant_record.tasks_monthly_limit
        task_pct = tasks_this_month / task_limit if task_limit else 0

        # Monthly cost vs limit
        cost_this_month = await db.scalar(
            select(func.coalesce(func.sum(ModelCall.cost_usd), 0))
            .select_from(ModelCall)
            .where(ModelCall.created_at >= month_start)
        ) or 0.0
        cost_limit = tenant_record.cost_monthly_limit_usd
        cost_pct = cost_this_month / cost_limit if cost_limit else 0

        usage_pcts = [agent_pct, task_pct, cost_pct]
        avg_usage_pct = int((sum(usage_pcts) / len(usage_pcts)) * 100)
        cost_budget_pct = int(cost_pct * 100)

        threshold = 0.9
        if agent_pct > threshold:
            exceeded.append("agents")
        if task_pct > threshold:
            exceeded.append("tasks")
        if cost_pct > threshold:
            exceeded.append("cost")

        if exceeded:
            quota_status = "degraded"
    else:
        # No tenant record = dev/admin context, quotas always healthy
        quota_status = "healthy"

    # ── 4. Cost health (24h trend) ─────────────────────────────────────────
    cost_today = await get_usage_stats(db, since=since_24h, tenant_id=tenant_id)
    cost_yesterday = await get_usage_stats(
        db,
        since=since_24h - timedelta(hours=24),
        until=since_24h,
        tenant_id=tenant_id,
    )

    cost_status = "healthy"
    today_usd = cost_today.get("total_cost_usd", 0.0)
    yesterday_usd = cost_yesterday.get("total_cost_usd", 0.0)
    if yesterday_usd > 0 and today_usd > yesterday_usd * 1.5:
        cost_status = "warning"

    # ── 5. Overall status ──────────────────────────────────────────────────
    if "degraded" in (agent_status, task_status, quota_status):
        overall = "degraded"
    else:
        overall = "healthy"

    return {
        "overall": overall,
        "checks": {
            "agents": {
                "status": agent_status,
                "running": len(running),
                "errored": len(errored),
                "total": len(agents),
            },
            "tasks": {
                "status": task_status,
                "pending": pending,
                "failed_24h": failed_24h,
                "total": total_tasks,
            },
            "quota": {
                "status": quota_status,
                "avg_usage_pct": avg_usage_pct,
                "exceeded": exceeded,
            },
            "cost": {
                "status": cost_status,
                "cost_24h_usd": round(today_usd, 2),
                "budget_pct": cost_budget_pct,
            },
            "last_updated": now.isoformat(),
        },
    }
