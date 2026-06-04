"""Celery tasks for agent self-optimization.

Runs weekly optimization across all tenants and agent types.
"""

import asyncio

from celery import shared_task

from app.core.database import async_session
from app.models.tenant import Tenant
from app.services.self_optimizer import SelfOptimizerService


@shared_task(bind=True)
def run_weekly_optimization(self):
    """Iterate all tenants, run optimize_agent for each active agent type.

    This runs weekly (Sunday 3am) via the Celery Beat schedule.
    """
    async def _run():
        async with async_session() as db:
            # Fetch all tenants
            from sqlalchemy import select
            stmt = select(Tenant)
            tenants = (await db.execute(stmt)).scalars().all()

            total_optimizations = 0
            for tenant in tenants:
                # Fetch distinct agent_types from AgentRun for this tenant
                from app.models.agent_run import AgentRun
                types_stmt = (
                    select(AgentRun.agent_type)
                    .where(AgentRun.tenant_id == tenant.id)
                    .distinct()
                )
                agent_types = (await db.execute(types_stmt)).scalars().all()

                for agent_type in agent_types:
                    log = await SelfOptimizerService.optimize_agent(
                        db, tenant.id, agent_type,
                    )
                    if log is not None:
                        total_optimizations += 1

            await db.commit()
            return {"optimizations_performed": total_optimizations}

    return asyncio.run(_run())
