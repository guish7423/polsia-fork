"""Audit chain REST API — GET entries, verify integrity."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import verify_api_key
from app.core.database import get_db
from app.core.tenant_context import get_current_tenant
from app.services.audit_chain import get_entries, verify_chain

router = APIRouter(prefix="/audit", tags=["audit"])


async def _require_tenant() -> int:
    """Extract tenant ID or raise 401."""
    tenant = get_current_tenant()
    if tenant is None or not hasattr(tenant, "id"):
        raise HTTPException(status_code=401, detail="No tenant context")
    return tenant.id


@router.get("/entries")
async def list_audit_entries(
    entry_type: str | None = Query(None, description="Filter by entry type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_api_key),
):
    """List audit entries for the current tenant."""
    tenant_id = await _require_tenant()
    entries = await get_entries(
        db, tenant_id, entry_type=entry_type, limit=limit, offset=offset
    )
    return {
        "entries": [
            {
                "id": e.id,
                "entry_type": e.entry_type,
                "entry_id": e.entry_id,
                "action": e.action,
                "hash": e.hash,
                "previous_hash": e.previous_hash,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ],
        "total": len(entries),
    }


@router.get("/verify")
async def verify_audit_chain(
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_api_key),
):
    """Verify the integrity of the audit chain."""
    tenant_id = await _require_tenant()
    broken = await verify_chain(db, tenant_id)
    return {
        "intact": len(broken) == 0,
        "broken_links": broken,
    }
