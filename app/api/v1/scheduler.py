"""Scheduler API router — resource-aware agent scheduling status and control.

Provides endpoints for querying scheduler status and triggering
queue rebalancing (admin).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.tenant_context import get_current_tenant
from app.services.agent_scheduler import AgentSchedulerService

router = APIRouter(prefix="/api/v1/scheduler", tags=["scheduler"])


@router.get("/status")
async def get_scheduler_status(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    current_tenant=Depends(get_current_tenant),
):
    """Return scheduler status and load metrics for the given tenant.

    Returns running/pending/queued counts, composite load score, and
    whether the threshold is exceeded.
    """
    if current_tenant is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Tenant context required")

    if current_tenant.id != tenant_id and current_tenant.id != 0:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Tenant mismatch")

    return await AgentSchedulerService.get_scheduler_status(db, tenant_id)


@router.post("/rebalance")
async def rebalance_queues(
    db: AsyncSession = Depends(get_db),
    current_tenant=Depends(get_current_tenant),
):
    """Admin: manually trigger queue rebalancing.

    Redistributes stuck or mis-queued agent tasks.
    """
    if current_tenant is None or current_tenant.id != 0:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Admin access required")

    count = await AgentSchedulerService.rebalance_queues(db)
    return {"redistributed": count}
