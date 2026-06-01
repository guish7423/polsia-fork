"""Lead REST endpoints — sales inquiry management."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.lead_service import (
    create_lead,
    get_leads,
    get_lead,
    update_lead_status,
    get_leads_summary,
)

router = APIRouter(tags=["leads"])


@router.post("/leads")
async def create_lead_endpoint(data: dict, db: AsyncSession = Depends(get_db)):
    if not data.get("name") or not data.get("email"):
        raise HTTPException(400, "name and email are required")
    lead = await create_lead(db, data)
    return {
        "id": lead.id,
        "name": lead.name,
        "email": lead.email,
        "status": lead.status,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
    }


@router.get("/leads")
async def list_leads(
    status: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    leads, total = await get_leads(db, status=status, limit=limit, offset=offset)
    return {
        "total": total,
        "data": [
            {
                "id": l.id,
                "name": l.name,
                "email": l.email,
                "company": l.company,
                "product_interest": l.product_interest,
                "status": l.status,
                "source_page": l.source_page,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in leads
        ],
    }


@router.get("/leads/summary")
async def leads_summary(db: AsyncSession = Depends(get_db)):
    return await get_leads_summary(db)


@router.get("/leads/{lead_id}")
async def get_lead_endpoint(lead_id: int, db: AsyncSession = Depends(get_db)):
    lead = await get_lead(db, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    return {
        "id": lead.id,
        "name": lead.name,
        "email": lead.email,
        "company": lead.company,
        "phone": lead.phone,
        "product_interest": lead.product_interest,
        "budget_range": lead.budget_range,
        "message": lead.message,
        "status": lead.status,
        "source_page": lead.source_page,
        "source_url": lead.source_url,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
    }


@router.post("/leads/{lead_id}/convert")
async def convert_lead(lead_id: int, data: dict = {}, db: AsyncSession = Depends(get_db)):
    """Convert a qualified lead into a CrossDeploy order."""
    from app.services.lead_service import convert_lead_to_order

    tier = data.get("tier", "basic")
    result = await convert_lead_to_order(db, lead_id, tier)
    if not result:
        raise HTTPException(404, "Lead not found")
    return {"ok": True, **result}


@router.patch("/leads/{lead_id}/status")
async def update_status(lead_id: int, data: dict, db: AsyncSession = Depends(get_db)):
    new_status = data.get("status")
    if not new_status:
        raise HTTPException(400, "status is required")
    try:
        lead = await update_lead_status(db, lead_id, new_status)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not lead:
        raise HTTPException(404, "Lead not found")
    return {"ok": True, "status": lead.status}
