"""Proposals API — AI-generated sales proposals for external orders."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import verify_api_key
from app.core.database import async_session
from app.models.external_order import ExternalOrder
from app.services.order_scanner_service import get_order
from app.config import settings
from app.services.email_service import (
    send_proposal_accepted,
    send_internal_notification,
)
from app.services.proposal_service import (
    accept_proposal,
    auto_generate_proposal,
    create_proposal,
    format_proposal,
    format_public_proposal,
    get_proposal_by_token,
    get_proposals,
    get_proposals_for_order,
    get_proposals_summary,
    get_proposal,
    reject_proposal,
    track_proposal_view,
    update_proposal_status,
)

router = APIRouter(dependencies=[Depends(verify_api_key)])

# Public router — no API key required
public_proposal_router = APIRouter(tags=["proposals-public"])


@public_proposal_router.get("/proposals/by-token/{view_token}")
async def get_proposal_by_token_endpoint(view_token: str):
    """Public endpoint — view a proposal by its shareable token. No auth required."""
    async with async_session() as db:
        p = await get_proposal_by_token(db, view_token)
        if not p:
            raise HTTPException(404, "Proposal not found")
        order = await get_order(db, p.order_id) if p.order_id else None
        return format_public_proposal(p, order)


@public_proposal_router.post("/proposals/by-token/{view_token}/accept")
async def accept_proposal_public(view_token: str):
    """Public endpoint — accept a proposal. No auth required.
    Auto-triggers DeployAgent fulfillment pipeline."""
    import json
    from sqlalchemy import update, select
    from app.models.external_order import ExternalOrder
    from app.agents.deploy_agent import DeployAgent

    async with async_session() as db:
        p = await get_proposal_by_token(db, view_token)
        if not p:
            raise HTTPException(404, "Proposal not found")
        if p.status not in ("draft", "sent", "replied", "negotiating"):
            raise HTTPException(400, f"Proposal is already {p.status}")
        updated = await accept_proposal(db, p.id)
        if not updated:
            raise HTTPException(500, "Failed to accept proposal")

        # Auto-trigger DeployAgent fulfillment
        deploy_plan = None
        customer_email = None
        if p.order_id:
            result = await db.execute(
                select(ExternalOrder).where(ExternalOrder.id == p.order_id)
            )
            order = result.scalar_one_or_none()
            if order:
                customer_email = order.customer_email
                try:
                    agent = DeployAgent()
                    deploy_plan = await agent.plan_deployment(db, order)
                    # Persist plan to provider_notes for portal
                    await db.execute(
                        update(ExternalOrder).where(ExternalOrder.id == order.id)
                        .values(provider_notes=json.dumps(deploy_plan, ensure_ascii=False))
                    )
                except Exception as e:
                    # Non-blocking — don't fail the accept if deploy fails
                    deploy_plan = {"error": str(e), "plan_summary": "Deployment plan generation deferred"}

        await db.commit()

        # Send email notifications (non-blocking on failure)
        view_url = f"{settings.base_url}/quote/{p.view_token}"
        customer_name = view_token  # fallback — real name extracted from order below
        if p.order_id:
            result = await db.execute(select(ExternalOrder).where(ExternalOrder.id == p.order_id))
            o = result.scalar_one_or_none()
            if o:
                customer_email = o.customer_email or customer_email
                # Derive name from order requirements: "Client: Name <email>"
                if o.requirements and o.requirements.startswith("Client: "):
                    customer_name = o.requirements.split("<")[0].replace("Client: ", "").strip()
                if customer_email:
                    send_proposal_accepted(customer_name, customer_email, view_url, o.title or "部署服务")
                    send_internal_notification(
                        "Proposal Accepted 🎉",
                        f"{customer_name} accepted proposal #{p.id} — {o.title}",
                        view_url,
                    )

        return {
            "status": "accepted",
            "proposal_id": p.id,
            "order_id": p.order_id,
            "deployment_plan": deploy_plan,
        }


@public_proposal_router.post("/proposals/by-token/{view_token}/reject")
async def reject_proposal_public(view_token: str, data: dict = {}):
    """Public endpoint — reject a proposal with optional reason. No auth required."""
    reason = data.get("reason", "") if isinstance(data, dict) else ""
    async with async_session() as db:
        p = await get_proposal_by_token(db, view_token)
        if not p:
            raise HTTPException(404, "Proposal not found")
        if p.status not in ("draft", "sent", "replied", "negotiating"):
            raise HTTPException(400, f"Proposal is already {p.status}")
        updated = await reject_proposal(db, p.id, reason)
        if not updated:
            raise HTTPException(500, "Failed to reject proposal")
        await db.commit()
        # Internal notification
        send_internal_notification(
            "Proposal Rejected",
            f"Proposal #{p.id} was rejected.\nReason: {reason or 'No reason given'}",
            f"{settings.base_url}/quote/{p.view_token}",
        )
        return {"status": "rejected", "proposal_id": p.id, "order_id": p.order_id}


@public_proposal_router.post("/proposals/by-token/{view_token}/track-view")
async def track_view(view_token: str):
    """Public endpoint — track a proposal view. No auth required."""
    async with async_session() as db:
        p = await get_proposal_by_token(db, view_token)
        if not p:
            raise HTTPException(404, "Proposal not found")
        updated = await track_proposal_view(db, p.id)
        if not updated:
            raise HTTPException(500, "Failed to track view")
        await db.commit()
        return {"viewed_count": updated.viewed_count, "viewed_at": updated.viewed_at.isoformat() if updated.viewed_at else None}


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
