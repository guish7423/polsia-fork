"""Supervisor Agent — smart task planning and goal decomposition.

Accepts a complex goal, decomposes it into sub-tasks with dependencies,
assigns each sub-task to the best-suited agent, and persists the plan.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BasePolsiaAgent, register_agent
from app.services.task_planner import (
    TaskPlan,
    assign_agent,
    create_tasks_from_plan,
    decompose_goal,
)
from app.services.activity_service import log_activity
from app.services.company_service import get_company


@register_agent
class SupervisorAgent(BasePolsiaAgent):
    """Strategic planner: decomposes goals, assigns agents, tracks dependencies."""

    agent_type = "supervisor"

    async def run(self, db: AsyncSession, context: dict | None = None) -> dict:
        """Execute the supervisor agent's primary logic.

        Args:
            db: Database session.
            context: Must contain a "goal" key. May optionally contain
                     "company_context" for richer decomposition.

        Returns:
            Dict with plan details, task IDs, and dependency chain.
        """
        context = context or {}
        goal = context.get("goal", "")
        if not goal:
            return {"error": "No goal provided", "result": "failed"}

        # Gather company context for richer planning
        company_config = await get_company(db)
        company_context = {
            "name": company_config.name if company_config else None,
            "industry": company_config.industry if company_config else None,
            "goals": company_config.goals if company_config else None,
            "mission": company_config.mission if company_config else None,
        } if company_config else {}

        # Step 1: Decompose the goal into sub-tasks
        plan: TaskPlan = await decompose_goal(goal, company_context)

        # Step 2: Assign agents and persist tasks
        created_tasks = await create_tasks_from_plan(db, plan)

        # Step 3: Build the response with task IDs and dependency chain
        task_results = []
        for i, sub_task in enumerate(plan.sub_tasks):
            db_task = created_tasks[i] if i < len(created_tasks) else None
            task_results.append({
                "task_id": db_task.id if db_task else None,
                "title": sub_task.get("title", ""),
                "agent_type": sub_task.get("agent_type", "orchestrator"),
                "priority": sub_task.get("priority", 3),
                "depends_on": sub_task.get("depends_on", []),
            })

        await log_activity(
            db,
            agent_type="supervisor",
            action="plan_created",
            summary=f"Decomposed goal '{goal[:60]}' into {len(plan.sub_tasks)} tasks",
        )

        return {
            "result": "plan_created",
            "goal": goal,
            "task_count": len(plan.sub_tasks),
            "dependency_graph": plan.dependency_graph,
            "tasks": task_results,
            "metadata": plan.metadata,
        }
