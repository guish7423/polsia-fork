"""Quota API router — per-tenant resource usage endpoint.

Used by the dashboard and service self-inspection to display current
quota consumption across all dimensions (agents, tasks, tokens, cost).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.tenant_context import get_current_tenant
from app.services.quota_service import get_quota_usage

router = APIRouter(prefix="/api/v1/tenants", tags=["quota"])


@router.get("/{tenant_id}/quota")
async def get_tenant_quota(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    current_tenant=Depends(get_current_tenant),
):
    """Return a full quota-usage snapshot for the given tenant.

    The caller must be the same tenant (tenant_id == current_tenant.id)
    unless they are the dev tenant (id=0).
    """
    if current_tenant is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Tenant context required")

    # Tenant isolation — only allow viewing your own quota
    if current_tenant.id != tenant_id and current_tenant.id != 0:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Tenant mismatch")

    usage = await get_quota_usage(db, tenant_id)

    # Serialize QuotaResult dataclasses to plain dicts for JSON response
    return {
        "tenant_id": tenant_id,
        "agents": {
            "allowed": usage["agents"].allowed,
            "reason": usage["agents"].reason,
            "current": usage["agents"].current,
            "limit": usage["agents"].limit,
            "usage_pct": round(usage["agents"].usage_pct, 4),
        },
        "tasks": {
            "allowed": usage["tasks"].allowed,
            "reason": usage["tasks"].reason,
            "current": usage["tasks"].current,
            "limit": usage["tasks"].limit,
            "usage_pct": round(usage["tasks"].usage_pct, 4),
        },
        "tokens": {
            "allowed": usage["tokens"].allowed,
            "reason": usage["tokens"].reason,
            "current": usage["tokens"].current,
            "limit": usage["tokens"].limit,
            "usage_pct": round(usage["tokens"].usage_pct, 4),
        },
        "cost": {
            "allowed": usage["cost"].allowed,
            "reason": usage["cost"].reason,
            "current": usage["cost"].current,
            "limit": usage["cost"].limit,
            "usage_pct": round(usage["cost"].usage_pct, 4),
        },
    }
