"""Evolution Office Agent — 进化办, analyzes performance and drives self-improvement."""

import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BasePolsiaAgent, register_agent
from app.agents.prompts import EVOLUTION_SYSTEM_PROMPT
from app.services.evolution_service import (
    get_agent_performance,
    generate_improvement_plan,
)
from app.services.activity_service import log_activity


@register_agent
class EvolutionOfficeAgent(BasePolsiaAgent):
    """Evolution Office — analyzes agent performance, trends, and generates
    improvement recommendations to drive continuous self-evolution."""

    agent_type = "evolution"

    async def run(self, db: AsyncSession, context: dict | None = None) -> dict:
        days = (context or {}).get("analysis_days", 7)

        # 1. Analyze agent performance
        performance = await get_agent_performance(db, days=days)

        # 2. Generate improvement plan
        plan = await generate_improvement_plan(db, performance)

        # 3. (Optional) LLM-powered deep analysis if there are issues worth examining
        llm_analysis = None
        if performance["suggestions"] and len(performance["suggestions"]) > 0:
            try:
                llm_input = json.dumps(
                    {"performance": performance, "plan": plan},
                    ensure_ascii=False,
                    default=str,
                )
                llm_result = await self.call_llm(
                    llm_input,
                    system_prompt=EVOLUTION_SYSTEM_PROMPT,
                )
                llm_analysis = json.loads(llm_result) if isinstance(llm_result, str) else llm_result
            except Exception:
                llm_analysis = {"analysis": "LLM analysis unavailable — rule-based analysis active."}
        else:
            llm_analysis = {"analysis": "All agents performing well, no evolution needed."}

        # 4. Log evolution activity
        action_count = performance["total_activities"]
        inactive = performance["inactive_agents"]
        suggestions = performance["suggestions"]

        summary_parts = [
            f"进化分析({days}天): {action_count}条活动, "
            f"{len(performance['agent_metrics'])}个Agent活跃"
        ]
        if inactive:
            summary_parts.append(f", {len(inactive)}个未激活")
        if suggestions and suggestions[0] != "所有 Agent 运行正常，无需优化":
            summary_parts.append(f", {len(suggestions)}条改进建议")
        else:
            summary_parts.append(", 状态良好")

        await log_activity(
            db=db,
            agent_type="evolution",
            action="analysis_cycle",
            summary="".join(summary_parts),
            level="info" if not suggestions or suggestions[0].startswith("所有") else "warning",
            detail={
                "period_days": days,
                "agent_count": len(performance["agent_metrics"]),
                "suggestion_count": len(suggestions),
                "inactive_agents": inactive,
            },
        )

        return {
            "performance": performance,
            "improvement_plan": plan,
            "llm_analysis": llm_analysis,
        }
