"""Deployment Agent — manages deployment lifecycle and status checks."""

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BasePolsiaAgent, register_agent
from app.agents.prompts import DEPLOYMENT_SYSTEM_PROMPT
from app.models.company_config import CompanyConfig
from app.services.activity_service import log_activity
from app.services.task_service import get_tasks


@register_agent
class DeploymentAgent(BasePolsiaAgent):
    """Checks deployment status and generates infrastructure reports."""

    agent_type = "deployment"

    async def run(self, db: AsyncSession, context: dict | None = None) -> dict:
        result = await db.execute(select(CompanyConfig).limit(1))
        config = result.scalar_one_or_none()

        pending_tasks = await get_tasks(db, status="pending", agent_type="deployment")
        in_progress_tasks = await get_tasks(db, status="in_progress", agent_type="deployment")

        prompt = json.dumps({
            "task": "Generate deployment status report",
            "company": config.name if config else "Unnamed Company",
            "website_url": config.website_url if config else None,
            "pending_deployments": len(pending_tasks),
            "active_deployments": len(in_progress_tasks),
        })

        llm_result = await self.call_llm(prompt, system_prompt=DEPLOYMENT_SYSTEM_PROMPT)

        await log_activity(
            db, agent_type="deployment", action="status_check",
            summary=f"Deployment status: {llm_result.get('status', 'unknown')}",
        )

        return {
            "result": "deployment_check_complete",
            "status": llm_result.get("status", "unknown"),
            "pending": len(pending_tasks),
            "in_progress": len(in_progress_tasks),
            "report": llm_result.get("report", ""),
        }
