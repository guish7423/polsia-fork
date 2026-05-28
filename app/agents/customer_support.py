"""CustomerSupport Agent — automated response generation and ticket monitoring."""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BasePolsiaAgent, register_agent
from app.models.social import SocialEngagement
from app.services.activity_service import log_activity


@register_agent
class CustomerSupportAgent(BasePolsiaAgent):
    """Monitors customer mentions and generates automated replies."""

    agent_type = "customer_support"

    async def run(self, db: AsyncSession, context: dict | None = None) -> dict:
        # Find unhandled mentions
        result = await db.execute(
            select(SocialEngagement).where(SocialEngagement.our_reply.is_(None)).limit(10)
        )
        pending = list(result.scalars().all())

        replies_generated = 0
        for mention in pending:
            prompt = json.dumps({
                "task": "Generate a customer support reply",
                "author": mention.author_handle,
                "original_message": mention.content,
                "tone": "helpful and professional",
                "instructions": (
                    "Output JSON with: "
                    '"reply" (str)'
                ),
            })

            llm_result = await self.call_llm(prompt)
            if "reply" in llm_result:
                mention.our_reply = llm_result["reply"]
                replies_generated += 1

        await db.flush()

        await log_activity(
            db, agent_type="customer_support", action="replies_generated",
            summary=f"Generated {replies_generated} replies for {len(pending)} pending mentions",
        )

        return {
            "result": "customer_support_complete",
            "pending_mentions": len(pending),
            "replies_generated": replies_generated,
        }
