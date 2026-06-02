"""Proposal service — AI-generated sales proposals for external orders."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.external_order import ExternalOrder
from app.models.proposal import Proposal
from app.models.task import Task


async def create_proposal(
    db: AsyncSession,
    order_id: int,
    proposed_amount: float | None = None,
    currency: str = "USD",
    content: str | None = None,
    summary: str | None = None,
    proposal_metadata: dict | None = None,
) -> Proposal:
    """Create a new proposal for an order."""
    proposal = Proposal(
        order_id=order_id,
        status="draft",
        proposed_amount=proposed_amount,
        currency=currency,
        content=content,
        summary=summary,
        proposal_metadata=proposal_metadata or {},
        view_token=uuid.uuid4().hex[:12],
    )
    db.add(proposal)
    await db.flush()
    await db.refresh(proposal)
    return proposal


async def get_proposal(db: AsyncSession, proposal_id: int) -> Proposal | None:
    result = await db.execute(
        select(Proposal).where(Proposal.id == proposal_id)
    )
    return result.scalar_one_or_none()


async def get_proposal_by_token(db: AsyncSession, view_token: str) -> Proposal | None:
    result = await db.execute(
        select(Proposal).where(Proposal.view_token == view_token)
    )
    return result.scalar_one_or_none()


async def get_proposals_for_order(db: AsyncSession, order_id: int) -> list[Proposal]:
    result = await db.execute(
        select(Proposal)
        .where(Proposal.order_id == order_id)
        .order_by(Proposal.created_at.desc())
    )
    return list(result.scalars().all())


async def get_proposals(
    db: AsyncSession,
    status: str | None = None,
    limit: int = 50,
) -> list[Proposal]:
    query = select(Proposal).order_by(Proposal.created_at.desc())
    if status:
        query = query.where(Proposal.status == status)
    query = query.limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def update_proposal_status(
    db: AsyncSession,
    proposal_id: int,
    status: str,
    proposed_amount: float | None = None,
) -> Proposal | None:
    proposal = await get_proposal(db, proposal_id)
    if not proposal:
        return None
    now = datetime.now(timezone.utc)
    proposal.status = status
    if status == "sent":
        proposal.sent_at = now
    elif status == "replied":
        proposal.replied_at = now
    elif status in ("won", "lost"):
        proposal.won_at = now if status == "won" else None
    if proposed_amount is not None:
        proposal.proposed_amount = proposed_amount
    await db.flush()
    await db.refresh(proposal)
    return proposal


async def get_proposals_summary(db: AsyncSession) -> dict:
    result = await db.execute(
        select(Proposal.status, func.count(Proposal.id))
        .group_by(Proposal.status)
    )
    rows = result.all()
    summary = {"total": sum(r[1] for r in rows)}
    for status, count in rows:
        summary[status] = count
    for s in ("draft", "sent", "replied", "negotiating", "won", "lost"):
        summary.setdefault(s, 0)
    return summary


async def auto_generate_proposal(
    db: AsyncSession, order: ExternalOrder
) -> Proposal | None:
    """Auto-generate a proposal for a scored/ready order.
    Returns None if order is not suitable."""
    if not order.score or order.score < 6:
        return None
    if not order.title:
        return None

    # Build proposal content from order context
    budget_mid = ((order.budget_min or 0) + (order.budget_max or 0)) / 2 if (order.budget_min or 0) > 0 and (order.budget_max or 0) > 0 else (order.budget_min or order.budget_max or 500)
    proposed_amount = max(budget_mid * 0.8, 100)  # 80% of mid-range as competitive bid

    content_parts = [
        f"## Proposal for: {order.title}",
        f"**Platform**: {order.platform}",
        f"**Estimated Budget**: {order.currency} {budget_mid:.0f}",
        f"**Our Bid**: {order.currency} {proposed_amount:.0f}",
        "",
        "### Our Approach",
        f"We have reviewed your requirements for **{order.title}** and believe CrossWave is the ideal partner.",
    ]

    if order.description:
        content_parts.extend([
            "",
            "### Understanding Your Needs",
            order.description[:500],
        ])

    content_parts.extend([
        "",
        "### Why CrossWave",
        "- **AI-Native Delivery**: Automated pipeline from deployment to monitoring",
        "- **Full-Stack Expertise**: FastAPI, Next.js, Docker, K8s, CI/CD",
        "- **24/7 Operations**: Autonomous AI agents monitor and optimize post-deployment",
        "- **Proven Track Record**: 10+ successful deployments (CrossBridge, CrossBlog, Polsia Fork)",
        "",
        "### Deliverables",
        "- Production-ready Docker containers",
        "- SSL/TLS with auto-renewal",
        "- CI/CD pipeline (GitHub Actions)",
        "- Health monitoring & alerting (Prometheus + Grafana)",
        "- 30-day post-deployment support",
        "",
        "### Timeline",
        "- Requirements validation: 1-2 days",
        "- Environment setup & deployment: 3-5 days",
        "- Testing & optimization: 2-3 days",
        "- Total: **5-10 business days**",
        "",
        "### Investment",
        f"**{order.currency} {proposed_amount:.0f}** (flat fee, no hidden costs)",
        "",
        "---",
        "Ready to get started? Reply to this proposal and we'll begin within 24 hours.",
    ])

    content = "\n".join(content_parts)

    proposal = await create_proposal(
        db,
        order_id=order.id,
        proposed_amount=round(proposed_amount),
        currency=order.currency or "USD",
        content=content,
        summary=f"AI-generated proposal for {order.title} — bid {order.currency} {proposed_amount:.0f}",
        proposal_metadata={
            "source": "auto_generate",
            "order_score": order.score,
            "budget_min": order.budget_min,
            "budget_max": order.budget_max,
            "platform": order.platform,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return proposal


def format_proposal(p: Proposal) -> dict:
    return {
        "id": p.id,
        "order_id": p.order_id,
        "status": p.status,
        "proposed_amount": p.proposed_amount,
        "currency": p.currency,
        "content": p.content,
        "summary": p.summary,
        "proposal_metadata": p.proposal_metadata,
        "view_token": p.view_token,
        "sent_at": p.sent_at.isoformat() if p.sent_at else None,
        "replied_at": p.replied_at.isoformat() if p.replied_at else None,
        "won_at": p.won_at.isoformat() if p.won_at else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def format_public_proposal(p: Proposal, order=None) -> dict:
    """Public-safe proposal representation — no internal fields exposed."""
    result = {
        "id": p.id,
        "status": p.status,
        "proposed_amount": p.proposed_amount,
        "currency": p.currency,
        "content": p.content,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "order_id": p.order_id,
        "view_token": p.view_token or "",
    }
    if order and hasattr(order, "deliverables") and order.deliverables:
        result["deliverables"] = order.deliverables
    return result
