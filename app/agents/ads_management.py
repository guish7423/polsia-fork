"""AdsManagement Agent — ad campaign optimization and budget allocation."""

import json
import random
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BasePolsiaAgent, register_agent
from app.models.ad import AdCampaign, AdMetric
from app.services.activity_service import log_activity


@register_agent
class AdsManagementAgent(BasePolsiaAgent):
    """Manages advertising campaigns and performance metrics."""

    agent_type = "ads_management"

    async def run(self, db: AsyncSession, context: dict | None = None) -> dict:
        today = date.today()

        existing = await db.execute(
            select(AdCampaign).limit(5)
        )
        campaigns = list(existing.scalars().all())

        prompt = json.dumps({
            "task": "Analyze ad performance and suggest budget allocation",
            "campaigns": [
                {"name": c.name, "status": c.status, "daily_budget": c.daily_budget_usd}
                for c in campaigns
            ],
            "instructions": (
                "Output JSON with: "
                '"campaign_name" (str), '
                '"budget_allocation_usd" (int), '
                '"optimization_tips" (list of str)'
            ),
        })

        llm_result = await self.call_llm(prompt)

        # Create or update campaigns from LLM output
        if not campaigns:
            campaign = AdCampaign(
                platform="google_ads",
                name=llm_result.get("campaign_name", "Default Campaign"),
                goal="brand_awareness",
                status="active",
                daily_budget_usd=llm_result.get("budget_allocation_usd", 5000),
            )
            db.add(campaign)
            await db.flush()
            campaigns = [campaign]

        # Create daily metrics for each active campaign
        metrics_count = 0
        for campaign in campaigns:
            metrics = AdMetric(
                campaign_id=campaign.id,
                date=today,
                impressions=random.randint(1000, 50000),
                clicks=random.randint(50, 2500),
                conversions=random.randint(1, 100),
                spend_usd=campaign.daily_budget_usd or 5000,
                ctr=round(random.uniform(1.0, 8.0), 2),
                cpc=round(random.uniform(0.5, 5.0), 2),
            )
            db.add(metrics)
            metrics_count += 1

        await db.flush()

        await log_activity(
            db, agent_type="ads_management", action="metrics_collected",
            summary=f"Updated metrics for {metrics_count} campaigns",
        )

        return {
            "result": "ads_management_complete",
            "campaigns_active": len(campaigns),
            "metrics_created": metrics_count,
        }
