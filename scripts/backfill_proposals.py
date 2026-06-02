"""Back-fill proposals for existing accepted/completed orders that lack them."""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import async_session
from app.services.order_scanner_service import get_orders, get_order
from app.services.proposal_service import auto_generate_proposal
from sqlalchemy import select
from app.models.external_order import ExternalOrder


async def main():
    async with async_session() as db:
        # Find accepted/completed orders without proposals
        result = await db.execute(
            select(ExternalOrder)
            .where(ExternalOrder.status.in_(["accepted", "completed"]))
            .order_by(ExternalOrder.id)
        )
        orders = list(result.scalars().all())
        
        # Filter out orders that already have proposals
        from app.models.proposal import Proposal
        missing = []
        for o in orders:
            exists = await db.execute(
                select(Proposal).where(Proposal.order_id == o.id).limit(1)
            )
            if not exists.scalar_one_or_none():
                missing.append(o)
        
        print(f"Found {len(missing)} orders missing proposals...")
        
        for o in missing:
            print(f"  Order #{o.id} ({o.status}, score={o.score}): {o.title[:60]}")
            proposal = await auto_generate_proposal(db, o)
            if proposal:
                print(f"    → Proposal #{proposal.id} ¥{proposal.proposed_amount:.0f}")
        
        await db.commit()
        print(f"\n✅ Generated {len(missing)} proposals")


if __name__ == "__main__":
    asyncio.run(main())
