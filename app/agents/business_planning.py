"""BusinessPlanning Agent — strategic planning and KPI refinement."""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BasePolsiaAgent, register_agent
from app.agents.prompts import BUSINESS_PLANNING_SYSTEM_PROMPT
from app.models.company_config import CompanyConfig
from app.services.activity_service import log_activity


@register_agent
class BusinessPlanningAgent(BasePolsiaAgent):
    """Analyzes company goals and suggests strategic adjustments."""

    agent_type = "business_planning"

    async def run(self, db: AsyncSession, context: dict | None = None) -> dict:
        result = await db.execute(select(CompanyConfig).limit(1))
        config = result.scalar_one_or_none()

        if not config:
            return {"result": "no_company_config", "message": "No company configured"}

        prompt = json.dumps({
            "task": "Analyze company strategy and suggest improvements",
            "company": config.name,
            "mission": config.mission,
            "vision": config.vision,
            "current_goals": config.goals,
            "current_kpis": config.kpis,
            "industry": config.industry,
        })

        llm_result = await self.call_llm(prompt, system_prompt=BUSINESS_PLANNING_SYSTEM_PROMPT)

        # Update company config with refined KPIs
        if llm_result.get("suggested_kpis"):
            config.kpis = llm_result["suggested_kpis"]
        if llm_result.get("suggested_goals"):
            config.goals = llm_result["suggested_goals"]

        await db.flush()

        recs = llm_result.get("recommendations", [])
        await log_activity(
            db, agent_type="business_planning", action="strategy_review",
            summary=f"Generated {len(recs)} strategic recommendations for {config.name}",
        )

        return {
            "result": "strategy_reviewed",
            "recommendations_count": len(recs),
            "kpis_updated": llm_result.get("suggested_kpis") is not None,
            "goals_updated": llm_result.get("suggested_goals") is not None,
        }
