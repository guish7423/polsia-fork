"""CodeGeneration Agent — generates code for company's product."""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BasePolsiaAgent, register_agent
from app.agents.prompts import CODE_GENERATION_SYSTEM_PROMPT
from app.models.company_config import CompanyConfig
from app.services.activity_service import log_activity
from app.services.task_service import create_task as create_task_record


@register_agent
class CodeGenerationAgent(BasePolsiaAgent):
    """Writes code templates for the company's product."""

    agent_type = "code_generation"

    async def run(self, db: AsyncSession, context: dict | None = None) -> dict:
        result = await db.execute(select(CompanyConfig).limit(1))
        config = result.scalar_one_or_none()

        prompt = json.dumps({
            "task": "Plan code generation for company product",
            "company": config.name if config else "Unnamed Company",
            "product_type": config.product_type if config else "web_app",
        })

        llm_result = await self.call_llm(prompt, system_prompt=CODE_GENERATION_SYSTEM_PROMPT)

        # Create deployment tasks from generated code output
        deployment_tasks = llm_result.get("deployment_tasks", [])
        tasks_created = 0
        for task_item in deployment_tasks:
            await create_task_record(
                db,
                title=task_item.get("title", "Deploy generated code"),
                agent_type="deployment",
                description=task_item.get("description", ""),
                source="code_generation",
            )
            tasks_created += 1

        files_generated = llm_result.get("generated_files", [])

        await db.flush()

        await log_activity(
            db, agent_type="code_generation", action="code_planned",
            summary=f"Planned {len(files_generated)} files, {tasks_created} deployment tasks",
        )

        return {
            "result": "code_generation_complete",
            "files_planned": len(files_generated),
            "deployment_tasks_created": tasks_created,
        }
