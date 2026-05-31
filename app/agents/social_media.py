"""SocialMedia Agent — content creation and publishing automation."""

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BasePolsiaAgent, register_agent
from app.agents.prompts import SOCIAL_MEDIA_SYSTEM_PROMPT
from app.models.social import SocialEngagement, SocialPost
from app.services.activity_service import log_activity


@register_agent
class SocialMediaAgent(BasePolsiaAgent):
    """Creates social media content and monitors engagement."""

    agent_type = "social_media"

    async def run(self, db: AsyncSession, context: dict | None = None) -> dict:
        prompt = json.dumps({
            "task": "Create social media content and analyze engagement",
        })

        llm_result = await self.call_llm(prompt, system_prompt=SOCIAL_MEDIA_SYSTEM_PROMPT)

        posts_created = 0
        for post_data in llm_result.get("posts", []):
            post = SocialPost(
                platform=post_data.get("platform", "twitter"),
                content=post_data.get("content", ""),
                status="draft",
                created_at=datetime.now(timezone.utc),
            )
            db.add(post)
            posts_created += 1

        # Check for unhandled mentions
        mention_result = await db.execute(
            select(SocialEngagement).where(SocialEngagement.our_reply.is_(None)).limit(5)
        )
        pending_mentions = list(mention_result.scalars().all())

        await db.flush()

        await log_activity(
            db, agent_type="social_media", action="content_created",
            summary=f"Created {posts_created} draft posts, {len(pending_mentions)} pending mentions",
        )

        return {
            "result": "social_media_run_complete",
            "posts_created": posts_created,
            "pending_mentions": len(pending_mentions),
        }
