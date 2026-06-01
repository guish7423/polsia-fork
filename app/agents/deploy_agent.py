"""Deploy Agent — plans and executes deployment tasks for CrossDeploy customers."""

import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BasePolsiaAgent, register_agent
from app.agents.prompts import DEPLOY_AGENT_SYSTEM_PROMPT
from app.models.external_order import ExternalOrder
from app.services.order_scanner_service import update_order_status


@register_agent
class DeployAgent(BasePolsiaAgent):
    """Plans and executes deployment tasks for CrossDeploy customers."""

    agent_type = "deploy_agent"

    async def run(self, db: AsyncSession, context: dict | None = None) -> dict:
        """Run deploy agent: find accepted deploy orders and plan them."""
        from sqlalchemy import select

        result = await db.execute(
            select(ExternalOrder).where(
                ExternalOrder.status == "accepted",
                ExternalOrder.assigned_agent == "deploy_agent",
            )
        )
        orders = list(result.scalars().all())
        plans = []
        for order in orders:
            plan = await self.plan_deployment(db, order)
            plans.append(plan)
            await update_order_status(db, order.id, "in_progress")
        return {"planned": len(plans), "plans": plans}

    async def plan_deployment(self, db: AsyncSession, order: ExternalOrder) -> dict:
        """Generate a deployment plan for an order."""
        tier = "basic"
        desc_lower = (order.description or "").lower()
        requirements = (order.requirements or "").lower()
        combined = desc_lower + requirements
        if "k8s" in combined or "kubernetes" in combined or "enterprise" in combined:
            tier = "enterprise"
        elif "postgres" in combined or "redis" in combined or "multi" in combined or "standard" in combined:
            tier = "standard"

        plan_prompt = json.dumps({
            "order_title": order.title,
            "description": order.description,
            "requirements": order.requirements,
            "tier": tier,
        })

        llm_result = await self.call_llm(
            plan_prompt, system_prompt=DEPLOY_AGENT_SYSTEM_PROMPT
        )

        return {
            "order_id": order.id,
            "title": order.title,
            "tier": llm_result.get("tier", tier),
            "plan_summary": llm_result.get("plan_summary", ""),
            "steps": llm_result.get("steps", []),
            "estimated_hours": llm_result.get("estimated_hours", 2),
            "deliverables": llm_result.get("deliverables", []),
        }
