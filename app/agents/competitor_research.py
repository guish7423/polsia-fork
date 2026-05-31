"""CompetitorResearch Agent — competitive analysis and market research."""

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BasePolsiaAgent, register_agent
from app.agents.prompts import COMPETITOR_RESEARCH_SYSTEM_PROMPT
from app.models.competitor import Competitor
from app.models.company_config import CompanyConfig
from app.services.activity_service import log_activity


@register_agent
class CompetitorResearchAgent(BasePolsiaAgent):
    """Analyzes competitive landscape and maintains competitor database."""

    agent_type = "competitor_research"

    async def run(self, db: AsyncSession, context: dict | None = None) -> dict:
        result = await db.execute(select(CompanyConfig).limit(1))
        config = result.scalar_one_or_none()

        comp_result = await db.execute(select(Competitor))
        existing = list(comp_result.scalars().all())
        existing_names = [c.name for c in existing]

        prompt = json.dumps({
            "task": "Competitive landscape analysis",
            "industry": config.industry if config else "technology",
            "company": config.name if config else "Unknown",
            "existing_competitors": existing_names,
        })

        llm_result = await self.call_llm(prompt, system_prompt=COMPETITOR_RESEARCH_SYSTEM_PROMPT)

        # Update or create competitor records
        competitors_data = llm_result.get("competitors", [])
        for comp_data in competitors_data:
            name = comp_data.get("name", "Unknown")
            match = next((c for c in existing if c.name == name), None)
            if match:
                match.weaknesses_json = comp_data.get("weaknesses", match.weaknesses_json)
                match.strengths_json = comp_data.get("strengths", match.strengths_json)
                match.last_researched = datetime.now(timezone.utc)
            else:
                competitor = Competitor(
                    name=name,
                    website=comp_data.get("website"),
                    positioning=comp_data.get("positioning"),
                    strengths_json=comp_data.get("strengths"),
                    weaknesses_json=comp_data.get("weaknesses"),
                    last_researched=datetime.now(timezone.utc),
                )
                db.add(competitor)

        await db.flush()

        await log_activity(
            db, agent_type="competitor_research", action="market_analysis",
            summary=f"Researched {len(competitors_data)} competitors",
        )

        return {
            "result": "competitors_updated",
            "competitors_found": len(competitors_data),
            "market_insights": llm_result.get("market_insights", ""),
        }
