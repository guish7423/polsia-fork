"""Lead service — CRUD + status transitions for sales inquiries."""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead

VALID_STATUSES = ("new", "contacted", "qualified", "proposal", "negotiation", "won", "lost")


async def create_lead(db: AsyncSession, data: dict) -> Lead:
    lead = Lead(
        name=data["name"],
        email=data["email"],
        company=data.get("company"),
        phone=data.get("phone"),
        product_interest=data.get("product_interest"),
        budget_range=data.get("budget_range"),
        message=data.get("message"),
        status=data.get("status", "new"),
        source_page=data.get("source_page"),
        source_url=data.get("source_url"),
    )
    db.add(lead)
    await db.flush()
    await db.refresh(lead)
    return lead


async def get_leads(
    db: AsyncSession, status: str | None = None, limit: int = 100, offset: int = 0
) -> tuple[list[Lead], int]:
    query = select(Lead)
    count_query = select(Lead.id)
    if status:
        query = query.where(Lead.status == status)
        count_query = count_query.where(Lead.status == status)
    total = await db.execute(count_query)
    total_count = len(total.scalars().all())
    result = await db.execute(
        query.order_by(Lead.created_at.desc()).offset(offset).limit(limit)
    )
    return list(result.scalars().all()), total_count


async def get_lead(db: AsyncSession, lead_id: int) -> Lead | None:
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    return result.scalar_one_or_none()


async def update_lead_status(db: AsyncSession, lead_id: int, status: str) -> Lead | None:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}. Must be one of {VALID_STATUSES}")
    result = await db.execute(
        update(Lead).where(Lead.id == lead_id).values(status=status).returning(Lead)
    )
    await db.commit()
    return result.scalar_one_or_none()


async def convert_lead_to_order(db: AsyncSession, lead_id: int, tier: str = "basic") -> dict | None:
    """Convert a qualified lead into a CrossDeploy external order."""
    from app.models.external_order import ExternalOrder
    from app.services.order_scanner_service import create_order

    lead = await get_lead(db, lead_id)
    if not lead:
        return None

    tiers = {"basic": {"title": f"CrossDeploy Basic — {lead.product_interest or lead.name}", "price": 2000, "currency": "CNY"},
             "standard": {"title": f"CrossDeploy Standard — {lead.product_interest or lead.name}", "price": 3000, "currency": "CNY"},
             "enterprise": {"title": f"CrossDeploy Enterprise — {lead.product_interest or lead.name}", "price": 5000, "currency": "CNY"}}
    cfg = tiers.get(tier, tiers["basic"])

    order = await create_order(
        db,
        title=cfg["title"],
        platform="internal",
        budget_min=cfg["price"],
        budget_max=cfg["price"],
        currency=cfg["currency"],
        description=lead.message,
        customer_email=lead.email,
        requirements=f"Client: {lead.name} <{lead.email}> | Company: {lead.company or 'N/A'} | Product interest: {lead.product_interest or 'N/A'} | Budget: {lead.budget_range or 'N/A'}",
    )
    await update_lead_status(db, lead_id, "won")
    return {"order_id": order.id, "tier": tier, "title": cfg["title"], "status": order.status}


async def get_leads_summary(db: AsyncSession) -> dict:
    result = await db.execute(select(Lead))
    all_leads = list(result.scalars().all())
    status_counts = {}
    for l in all_leads:
        s = l.status
        status_counts[s] = status_counts.get(s, 0) + 1
    return {
        "total": len(all_leads),
        "status_distribution": status_counts,
        "new_count": status_counts.get("new", 0),
    }
