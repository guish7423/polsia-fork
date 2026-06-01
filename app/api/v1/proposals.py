"""Proposals API — AI-generated sales proposals for external orders."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import verify_api_key
from app.core.database import async_session
from app.services.order_scanner_service import get_order
from app.services.proposal_service import (
    auto_generate_proposal,
    create_proposal,
    format_proposal,
    get_proposals,
    get_proposals_for_order,
    get_proposals_summary,
    get_proposal,
    update_proposal_status,
)

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/proposals")
async def list_proposals(status: str = "", limit: int = Query(50, le=200)):
    async with async_session() as db:
        data = await get_proposals(db, status or None, limit)
        return {"data": [format_proposal(p) for p in data], "total": len(data)}


@router.get("/proposals/summary")
async def proposals_summary():
    async with async_session() as db:
        return await get_proposals_summary(db)


@router.post("/proposals")
async def create_proposal_endpoint(
    order_id: int,
    proposed_amount: float | None = None,
    currency: str = "USD",
    content: str | None = None,
    summary: str | None = None,
):
    async with async_session() as db:
        proposal = await create_proposal(db, order_id, proposed_amount, currency, content, summary)
        await db.commit()
        return format_proposal(proposal)


@router.post("/proposals/auto-generate/{order_id}")
async def auto_generate(order_id: int):
    """Auto-generate a proposal from an order using AI templates."""
    async with async_session() as db:
        order = await get_order(db, order_id)
        if not order:
            raise HTTPException(404, "Order not found")
        proposal = await auto_generate_proposal(db, order)
        if not proposal:
            raise HTTPException(400, "Order not suitable for auto-generation (score < 6)")
        await db.commit()
        return format_proposal(proposal)


@router.get("/proposals/{proposal_id}")
async def get_proposal_endpoint(proposal_id: int):
    async with async_session() as db:
        p = await get_proposal(db, proposal_id)
        if not p:
            raise HTTPException(404, "Proposal not found")
        return format_proposal(p)


@router.get("/proposals/by-order/{order_id}")
async def proposals_by_order(order_id: int):
    async with async_session() as db:
        items = await get_proposals_for_order(db, order_id)
        return {"data": [format_proposal(p) for p in items]}


@router.patch("/proposals/{proposal_id}/status")
async def change_proposal_status(
    proposal_id: int,
    status: str,
    proposed_amount: float | None = None,
):
    valid = ("draft", "sent", "replied", "negotiating", "won", "lost")
    if status not in valid:
        raise HTTPException(400, f"Invalid status. Must be one of: {', '.join(valid)}")
    async with async_session() as db:
        p = await update_proposal_status(db, proposal_id, status, proposed_amount)
        if not p:
            raise HTTPException(404, "Proposal not found")
        await db.commit()
        return format_proposal(p)
