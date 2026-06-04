"""Quota service — per-tenant resource limit checks.

Each check compares current usage (count or aggregation) against the
tenant's configured limit and returns a ``QuotaResult`` dataclass.

All checks are scoped to the **current calendar month**.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.models.agent_run import AgentRun
from app.models.model_call import ModelCall
from app.models.task import Task
from app.models.tenant import Tenant


# ─── QuotaResult ──────────────────────────────────────────────────────────────


@dataclass
class QuotaResult:
    """Result of a single quota check."""

    allowed: bool
    reason: str | None = None
    current: int | float = 0
    limit: int | float = 0
    usage_pct: float = 0.0


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _month_start() -> datetime:
    """Return the start of the current calendar month (UTC)."""
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


# ─── Quota checks ─────────────────────────────────────────────────────────────


async def check_agent_quota(db: AsyncSession, tenant_id: int) -> QuotaResult:
    """Check that the number of **running** agent runs is below the limit."""
    count_q = select(func.count()).select_from(AgentRun).where(
        AgentRun.tenant_id == tenant_id,
        AgentRun.status == "running",
    )
    count = (await db.execute(count_q)).scalar() or 0

    tenant = await db.get(Tenant, tenant_id)
    limit = tenant.agents_limit if tenant else 0

    usage_pct = count / limit if limit else 1.0
    # ── Alert injection: quota > 90% ──────────────────────────────────────
    if usage_pct > 0.9 and tenant_id > 0:
        await _try_fire_quota_alert(db, tenant_id, "agent", usage_pct)
    return QuotaResult(
        allowed=count < limit,
        reason=None if count < limit else "agent_limit_exceeded",
        current=count,
        limit=limit,
        usage_pct=usage_pct,
    )


async def check_tasks_monthly_quota(db: AsyncSession, tenant_id: int) -> QuotaResult:
    """Check tasks created this month against the monthly limit."""
    start = _month_start()
    count_q = (
        select(func.count())
        .select_from(Task)
        .where(Task.tenant_id == tenant_id, Task.created_at >= start)
    )
    count = (await db.execute(count_q)).scalar() or 0

    tenant = await db.get(Tenant, tenant_id)
    limit = tenant.tasks_monthly_limit if tenant else 0
    usage_pct = count / limit if limit else 1.0

    # ── Alert injection: task quota > 90% ─────────────────────────────────
    if usage_pct > 0.9 and tenant_id > 0:
        await _try_fire_quota_alert(db, tenant_id, "tasks", usage_pct)

    return QuotaResult(
        allowed=count < limit,
        reason=None if count < limit else "tasks_monthly_limit_exceeded",
        current=count,
        limit=limit,
        usage_pct=usage_pct,
    )


async def check_token_budget(db: AsyncSession, tenant_id: int) -> QuotaResult:
    """Check total tokens used this month against the monthly token limit."""
    start = _month_start()
    total_q = (
        select(func.coalesce(func.sum(ModelCall.input_tokens), 0) + func.coalesce(func.sum(ModelCall.output_tokens), 0))
        .select_from(ModelCall)
        .where(ModelCall.tenant_id == tenant_id, ModelCall.created_at >= start)
    )
    total = (await db.execute(total_q)).scalar() or 0

    tenant = await db.get(Tenant, tenant_id)
    limit = tenant.tokens_monthly_limit if tenant else 0
    usage_pct = (total or 0) / limit if limit else 1.0

    # ── Alert injection: token quota > 90% ────────────────────────────────
    if usage_pct > 0.9 and tenant_id > 0:
        await _try_fire_quota_alert(db, tenant_id, "tokens", usage_pct)

    return QuotaResult(
        allowed=(total or 0) < limit,
        reason=None if (total or 0) < limit else "token_budget_exceeded",
        current=total or 0,
        limit=limit,
        usage_pct=usage_pct,
    )


async def check_cost_budget(db: AsyncSession, tenant_id: int) -> QuotaResult:
    """Check total cost this month against the monthly cost limit.

    Aggregates ``cost_usd`` from ``ModelCall`` records.
    """
    start = _month_start()
    total_q = (
        select(func.coalesce(func.sum(ModelCall.cost_usd), 0.0))
        .select_from(ModelCall)
        .where(ModelCall.tenant_id == tenant_id, ModelCall.created_at >= start)
    )
    total = (await db.execute(total_q)).scalar() or 0.0

    tenant = await db.get(Tenant, tenant_id)
    limit = tenant.cost_monthly_limit_usd if tenant else 0
    usage_pct = float(total) / limit if limit else 1.0

    # ── Alert injection: cost quota > 90% ─────────────────────────────────
    if usage_pct > 0.9 and tenant_id > 0:
        await _try_fire_quota_alert(db, tenant_id, "cost", usage_pct)

    return QuotaResult(
        allowed=float(total) < limit,
        reason=None if float(total) < limit else "cost_budget_exceeded",
        current=round(float(total), 6),
        limit=limit,
        usage_pct=usage_pct,
    )


# ─── Alert injection helper ─────────────────────────────────────────────────────

async def _try_fire_quota_alert(
    db: AsyncSession,
    tenant_id: int,
    dimension: str,
    usage_pct: float,
) -> None:
    """Fire-and-forget quota warning alert (lazy import, fail-open)."""
    try:
        from app.services.alert_service import AlertService

        await AlertService.from_quota_warning(
            db,
            tenant_id=tenant_id,
            source=f"quota:{dimension}",
            usage_pct=usage_pct,
        )
    except Exception:
        logger.exception(
            "Failed to fire quota alert for dimension=%s (tenant=%d)",
            dimension, tenant_id,
        )


# ─── Dashboard convenience ────────────────────────────────────────────────────


async def get_quota_usage(db: AsyncSession, tenant_id: int) -> dict:
    """Return a full quota-usage snapshot for all dimensions.

    Intended for dashboard and service self-inspection.
    """
    return {
        "agents": await check_agent_quota(db, tenant_id),
        "tasks": await check_tasks_monthly_quota(db, tenant_id),
        "tokens": await check_token_budget(db, tenant_id),
        "cost": await check_cost_budget(db, tenant_id),
    }
