"""Orchestrator/CEO Agent — daily planning and agent coordination."""

import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BasePolsiaAgent, register_agent
from app.models.company_config import CompanyConfig
from app.models.report import DailyReport
from app.services.activity_service import log_activity
from app.services.task_service import create_task as create_task_record


@register_agent
class OrchestratorAgent(BasePolsiaAgent):
    """CEO agent: creates daily plan, assigns tasks, generates reports."""

    agent_type = "orchestrator"

    async def run(self, db: AsyncSession, context: dict | None = None) -> dict:
        # Read company config for context
        result = await db.execute(select(CompanyConfig).limit(1))
        config = result.scalar_one_or_none()
        company_name = config.name if config else "Unnamed Company"
        goals = config.goals if config and config.goals else {}

        # Build prompt for LLM
        prompt = json.dumps({
            "task": "Create a daily plan and prioritized task list",
            "company": company_name,
            "goals": goals,
            "date": date.today().isoformat(),
            "instructions": (
                "Output a JSON object with: "
                '"morning_plan" (str), "tasks" (list of {title, description, agent_type, priority})'
            ),
        })

        llm_result = await self.call_llm_async(prompt)

        # Create tasks from LLM output
        tasks_planned = 0
        for task_item in llm_result.get("tasks", []):
            agent_type = task_item.get("agent_type", "orchestrator")
            await create_task_record(
                db,
                title=task_item.get("title", "Unnamed task"),
                agent_type=agent_type,
                description=task_item.get("description"),
                priority=task_item.get("priority", 3),
                source="orchestrator",
            )
            tasks_planned += 1

        # Create/update daily report
        today = date.today()
        report_result = await db.execute(
            select(DailyReport).where(DailyReport.report_date == today)
        )
        report = report_result.scalar_one_or_none()
        if not report:
            report = DailyReport(
                report_date=today,
                morning_plan=llm_result.get("morning_plan", ""),
                tasks_planned=tasks_planned,
            )
            db.add(report)
        else:
            report.morning_plan = llm_result.get("morning_plan", "")
            report.tasks_planned = tasks_planned

        await db.flush()

        await log_activity(
            db, agent_type="orchestrator", action="daily_plan",
            summary=f"Planned {tasks_planned} tasks for {company_name}",
        )

        return {
            "result": "daily_plan_created",
            "company": company_name,
            "tasks_planned": tasks_planned,
        }
