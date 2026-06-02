"""Proposal Nurture Service — automatic follow-up for unread proposals.

Scans proposals sent >= 3 days with 0 views and creates activity_log
entries so the HQ notifications system can surface them for follow-up.
"""

from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.proposal import Proposal
from app.models.activity_log import ActivityLog


async def scan_proposals_needing_nurture(
    db: AsyncSession,
    min_age_days: int = 3,
) -> list[dict]:
    """Find sent proposals with 0 views that are >= `min_age_days` old.

    Returns a list of dicts suitable for creating follow-up activity logs.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=min_age_days)
    result = await db.execute(
        select(Proposal)
        .where(
            Proposal.status == "sent",
            Proposal.sent_at <= cutoff,
            (Proposal.viewed_count == 0) | (Proposal.viewed_count.is_(None)),
        )
        .order_by(Proposal.sent_at.asc())
    )
    proposals = list(result.scalars().all())

    results = []
    for p in proposals:
        sent_days = (datetime.now(timezone.utc) - p.sent_at).days if p.sent_at else min_age_days
        results.append({
            "proposal_id": p.id,
            "order_id": p.order_id,
            "amount": p.proposed_amount,
            "currency": p.currency,
            "sent_days_ago": sent_days,
            "view_token": p.view_token,
        })
    return results


async def create_nurture_activities(
    db: AsyncSession,
    proposals: list[dict],
) -> list[ActivityLog]:
    """Create activity_log entries for proposals needing follow-up."""
    created = []
    for p in proposals:
        log = ActivityLog(
            agent_type="proposal_nurture",
            action="proposal_needs_followup",
            summary=(
                f"Proposal #{p['proposal_id']} — {p['currency']} {p['amount']:.0f} "
                f"sent {p['sent_days_ago']}d ago, not viewed yet"
            ),
            detail={
                "proposal_id": p["proposal_id"],
                "order_id": p["order_id"],
                "amount": p["amount"],
                "currency": p["currency"],
                "sent_days_ago": p["sent_days_ago"],
                "view_token": p["view_token"],
                "action_needed": "follow_up_with_client",
            },
            level="warning",
        )
        db.add(log)
        created.append(log)
    if created:
        await db.flush()
    return created


async def run_nurture_check(db: AsyncSession) -> dict:
    """Full nurture check: scan + create activities.

    Returns summary of what was found and created.
    """
    needing = await scan_proposals_needing_nurture(db)
    created = await create_nurture_activities(db, needing) if needing else []
    return {
        "proposals_found": len(needing),
        "activities_created": len(created),
        "proposals": [
            {
                "id": p["proposal_id"],
                "amount": p["amount"],
                "currency": p["currency"],
                "sent_days_ago": p["sent_days_ago"],
            }
            for p in needing
        ],
    }
