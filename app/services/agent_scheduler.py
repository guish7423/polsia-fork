"""Resource-aware agent scheduling service.

Calculates per-tenant load based on running agents, pending tasks,
and recent token usage, then dispatches to the appropriate Celery queue
(default or low_priority).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_run import AgentRun
from app.models.model_call import ModelCall
from app.models.task import Task
from app.models.tenant import Tenant

LOAD_THRESHOLD: float = 0.80
"""Fraction of the tenant's agents_limit at which we consider them overloaded."""

_RUNNING_WEIGHT = 0.4
_PENDING_WEIGHT = 0.3
_TOKEN_WEIGHT = 0.3


class AgentSchedulerService:
    """Resource-aware agent scheduler.

    All methods are ``@staticmethod`` or ``@classmethod`` so they can be
    called without instantiation.
    """

    @staticmethod
    async def schedule_agent(
        db: AsyncSession,
        agent_type: str,
        tenant_id: int,
        priority: int = 0,
    ) -> str:
        """Decide which Celery queue an agent run should be dispatched to.

        Args:
            db: Database session.
            agent_type: The type of agent being scheduled.
            tenant_id: Tenant scope for load calculation.
            priority: Caller-supplied priority hint (currently unused).

        Returns:
            ``"low_priority"`` when the tenant is overloaded,
            ``"default"`` otherwise.
        """
        load_score = await _calculate_load(db, tenant_id)
        tenant = await db.get(Tenant, tenant_id)
        limit = tenant.agents_limit if tenant else 1

        # Guard against division by zero
        effective_limit = max(limit, 1)
        ratio = load_score / effective_limit

        if ratio > LOAD_THRESHOLD:
            return "low_priority"
        return "default"

    @staticmethod
    async def get_scheduler_status(
        db: AsyncSession,
        tenant_id: int,
    ) -> dict:
        """Return a snapshot of scheduler metrics for the given tenant.

        Returns:
            dict with keys: running, pending, queued, load_score,
            threshold_exceeded.
        """
        running = await _count_running_agents(db, tenant_id)
        pending = await _count_pending_tasks(db, tenant_id)
        load_score = await _calculate_load(db, tenant_id)

        tenant = await db.get(Tenant, tenant_id)
        limit = tenant.agents_limit if tenant else 1
        effective_limit = max(limit, 1)
        ratio = load_score / effective_limit

        return {
            "tenant_id": tenant_id,
            "running": running,
            "pending": pending,
            "queued": 0,  # Placeholder — would require Celery inspection
            "load_score": round(load_score, 4),
            "agents_limit": limit,
            "threshold_exceeded": ratio > LOAD_THRESHOLD,
        }

    @staticmethod
    async def rebalance_queues(db: AsyncSession) -> int:
        """Admin operation: redistribute stuck or mis-queued items.

        Currently a no-op that returns 0. Future iterations could inspect
        Celery queue lengths and move tasks between queues.

        Returns:
            Number of items redistributed (always 0 in this version).
        """
        # TODO: Implement actual queue inspection and redistribution
        # using Celery app.control.inspect() and app.control.purge().
        return 0


# ─── Internal helpers ─────────────────────────────────────────────────────────


async def _count_running_agents(db: AsyncSession, tenant_id: int) -> int:
    """Return the number of currently running agents for the tenant."""
    count_q = select(func.count()).select_from(AgentRun).where(
        AgentRun.tenant_id == tenant_id,
        AgentRun.status == "running",
    )
    return (await db.execute(count_q)).scalar() or 0


async def _count_pending_tasks(db: AsyncSession, tenant_id: int) -> int:
    """Return the number of pending tasks for the tenant."""
    count_q = select(func.count()).select_from(Task).where(
        Task.tenant_id == tenant_id,
        Task.status == "pending",
    )
    return (await db.execute(count_q)).scalar() or 0


async def _recent_token_usage(db: AsyncSession, tenant_id: int) -> int:
    """Return total tokens used in the last 5 minutes by the tenant."""
    five_min_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
    total_q = (
        select(
            func.coalesce(func.sum(ModelCall.input_tokens), 0)
            + func.coalesce(func.sum(ModelCall.output_tokens), 0)
        )
        .select_from(ModelCall)
        .where(
            ModelCall.tenant_id == tenant_id,
            ModelCall.created_at >= five_min_ago,
        )
    )
    return (await db.execute(total_q)).scalar() or 0


async def _calculate_load(db: AsyncSession, tenant_id: int) -> float:
    """Calculate the composite load score for a tenant.

    ``load_score = running * 0.4 + pending * 0.3 + (tokens_5min / 100_000) * 0.3``
    """
    running = await _count_running_agents(db, tenant_id)
    pending = await _count_pending_tasks(db, tenant_id)
    tokens = await _recent_token_usage(db, tenant_id)

    return (
        running * _RUNNING_WEIGHT
        + pending * _PENDING_WEIGHT
        + (tokens / 100_000) * _TOKEN_WEIGHT
    )
