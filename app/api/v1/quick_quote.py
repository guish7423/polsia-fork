"""Quick Quote endpoint — one-call lead-to-proposal pipeline.

Accepts form data, creates a Lead, converts it to an ExternalOrder,
auto-generates a Proposal and Deliverables, then marks the proposal as sent.
"""

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.lead_service import create_lead, convert_lead_to_order
from app.services.proposal_service import (
    auto_generate_proposal,
    update_proposal_status,
)
from app.services.order_deliverable_service import (
    generate_standard_deliverables,
    save_deliverables,
)
from app.services.order_scanner_service import get_order
from app.services.email_service import send_proposal_sent
from app.config import settings

router = APIRouter(tags=["quick-quote"])


# ── Helpers ────────────────────────────────────────────────────────────────


def _detect_tier(budget_range: str | None, preferred: str | None) -> str:
    """Auto-detect pricing tier from budget range, or use preferred if given."""
    if preferred and preferred in ("basic", "standard", "enterprise"):
        return preferred
    if not budget_range:
        return "basic"
    numbers = re.findall(r"\d+", budget_range)
    nums = [int(n) for n in numbers if n.isdigit()]
    max_val = max(nums) if nums else 0
    if max_val >= 4000:
        return "enterprise"
    if max_val >= 2000:
        return "standard"
    return "basic"


# ── Endpoint ───────────────────────────────────────────────────────────────


@router.post("/quick-quote")
async def quick_quote(data: dict, db: AsyncSession = Depends(get_db)):
    """Create a lead, convert to order, generate proposal + deliverables,
    and mark as sent — all in one call."""
    name = data.get("name")
    email = data.get("email")
    if not name or not email:
        raise HTTPException(400, "name and email are required")

    project_description = data.get("project_description", "")
    budget_range = data.get("budget_range")
    preferred_tier = data.get("preferred_tier")
    tier = _detect_tier(budget_range, preferred_tier)

    # 1. Create Lead
    lead = await create_lead(
        db,
        {
            "name": name,
            "email": email,
            "company": data.get("company"),
            "phone": data.get("phone"),
            "product_interest": "Quick Quote",
            "budget_range": budget_range,
            "message": project_description,
            "status": "new",
        },
    )

    # 2. Convert Lead → ExternalOrder
    conv = await convert_lead_to_order(db, lead.id, tier)
    if not conv:
        raise HTTPException(500, "Failed to convert lead to order")
    order_id = conv["order_id"]

    # 3. Fetch the order and ensure it passes the score gate for proposals
    order = await get_order(db, order_id)
    if not order:
        raise HTTPException(500, "Order not found after conversion")
    order.score = 10  # bypass auto_generate_proposal's score >= 6 check

    # 4. Auto-generate Proposal (reads order.score from the Python object)
    proposal = await auto_generate_proposal(db, order)
    if not proposal:
        raise HTTPException(500, "Failed to auto-generate proposal")

    # 5. Generate and save Deliverables
    deliverables = generate_standard_deliverables(
        order_title=order.title,
        description=order.description or "",
        requirements=order.requirements or "",
        tier=tier,
        order_id=order.id,
    )
    await save_deliverables(
        db, order_id, deliverables, delivery_notes="Auto-generated via Quick Quote"
    )

    # 6. Mark proposal as sent (sets status='sent' + sent_at timestamp)
    updated = await update_proposal_status(db, proposal.id, "sent")
    if not updated:
        raise HTTPException(500, "Failed to mark proposal as sent")

    # 7. Send email notification to customer (non-blocking on failure)
    tiers_label = {"basic": "¥2,000", "standard": "¥3,000", "enterprise": "¥5,000"}
    view_url = f"{settings.base_url}/quote/{proposal.view_token}"
    send_proposal_sent(
        name=name,
        email=email,
        view_url=view_url,
        amount=tiers_label.get(tier, tiers_label["basic"]),
        summary=proposal.summary or f"Quick Quote for {order.title}",
        order_title=order.title,
    )

    return {
        "order_id": order_id,
        "proposal_id": proposal.id,
        "status": "sent",
        "view_token": proposal.view_token,
        "view_url": view_url,
    }
