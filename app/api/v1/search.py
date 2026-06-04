"""Search API — cross-model unified search endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.tenant_context import get_current_tenant
from app.services.search_service import SEARCHABLE_TYPES, search_all

router = APIRouter(tags=["search"])


@router.get("/search")
async def global_search(
    q: str = Query("", min_length=0, description="Search keyword"),
    types: str = Query(
        None,
        description=f"Comma-separated type filter. Options: {', '.join(SEARCHABLE_TYPES)}",
    ),
    limit: int = Query(default=20, ge=1, le=100, description="Max results"),
    db: AsyncSession = Depends(get_db),
):
    """Cross-model search across tasks, agents, alerts, and runs.

    Returns unified results sorted by relevance (exact match > fuzzy match > newer).
    Results are scoped to the current tenant.
    """
    tenant = get_current_tenant()
    # 0 = dev/admin mode — no tenant isolation
    tenant_id = tenant.id if tenant and tenant.id != 0 else None

    type_list = None
    if types:
        type_list = [t.strip() for t in types.split(",") if t.strip() in SEARCHABLE_TYPES]

    results = await search_all(
        db=db,
        q=q.strip(),
        types=type_list,
        limit=limit,
        tenant_id=tenant_id,
    )
    return results
