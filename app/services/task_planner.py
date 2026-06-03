"""Smart task planning — goal decomposition, agent assignment, plan persistence."""

import json
from dataclasses import dataclass, field, asdict

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.task_service import create_task, VALID_AGENT_TYPES


@dataclass
class TaskPlan:
    """Structured plan produced by the supervisor agent."""

    goal: str
    sub_tasks: list[dict] = field(default_factory=list)
    dependency_graph: dict[str, list[str]] = field(default_factory=dict)
    metadata: dict | None = None


# ─── Agent assignment logic ────────────────────────────────────────────────

# Keywords → agent type mapping for smart task routing
_AGENT_ROUTES: dict[str, str] = {
    "competitor": "competitor_research",
    "market": "competitor_research",
    "research": "competitor_research",
    "social": "social_media",
    "twitter": "social_media",
    "linkedin": "social_media",
    "email": "email_outreach",
    "outreach": "email_outreach",
    "customer": "customer_support",
    "support": "customer_support",
    "ad": "ads_management",
    "ads": "ads_management",
    "campaign": "ads_management",
    "code": "code_generation",
    "feature": "code_generation",
    "implement": "code_generation",
    "finance": "finance",
    "revenue": "finance",
    "report": "finance",
    "deploy": "deployment",
    "release": "deployment",
    "strategy": "business_planning",
    "planning": "business_planning",
    "kpi": "business_planning",
}


def assign_agent(sub_task: dict) -> str:
    """Match a sub-task to the best agent type based on keywords and content.

    Falls back to the orchestrator if no good match is found.
    """
    title = (sub_task.get("title") or "").lower()
    description = (sub_task.get("description") or "").lower()
    combined = f"{title} {description}"

    for keyword, agent_type in _AGENT_ROUTES.items():
        if keyword in combined:
            if agent_type in VALID_AGENT_TYPES:
                return agent_type

    # Orchestrator is the safe fallback
    return "orchestrator"


# ─── LLM-powered goal decomposition ────────────────────────────────────────

_DECOMPOSE_SYSTEM_PROMPT = """You are a senior project planner. Break down a complex goal
into concrete, assignable sub-tasks. For each task, determine its dependencies and
provide enough context for an agent to execute it.

Output JSON with this exact structure:
{
  "sub_tasks": [
    {
      "id": "task-1",
      "title": "Short task name",
      "description": "Detailed description of what to do",
      "agent_type_hint": "suggested agent type or general",
      "priority": 3,
      "depends_on": ["task-0"]
    }
  ],
  "dependency_graph": {
    "task-1": ["task-0"],
    "task-2": ["task-1"]
  },
  "metadata": {
    "estimated_complexity": "low|medium|high",
    "note": "Any additional context"
  }
}

Rules:
- Each task ID must be unique (task-0, task-1, ...).
- "depends_on" lists task IDs that must complete before this one.
- Use "depends_on": [] for independent tasks.
- Keep descriptions actionable — an agent should know what "done" looks like.
- Assign priority 1-5 (5 = highest)."""


async def decompose_goal(goal: str, company_context: dict | None = None) -> TaskPlan:
    """Use LLM to decompose a complex goal into a structured TaskPlan.

    Args:
        goal: The high-level goal or request.
        company_context: Optional dict with company name, industry, goals, etc.

    Returns:
        A TaskPlan with sub-tasks, dependency graph, and metadata.
    """
    from app.agents.base import BasePolsiaAgent

    context_str = json.dumps(company_context or {}, indent=2)
    prompt = json.dumps({
        "goal": goal,
        "company_context": context_str,
        "instructions": (
            "Decompose this goal into 2-6 concrete sub-tasks. "
            "Each sub-task should be executable by a single agent. "
            "Identify clear dependencies between tasks."
        ),
    })

    # Use a temporary base agent for the LLM call
    agent = BasePolsiaAgent()
    llm_result = await agent.call_llm(prompt, system_prompt=_DECOMPOSE_SYSTEM_PROMPT)

    sub_tasks = llm_result.get("sub_tasks", [])
    dependency_graph = llm_result.get("dependency_graph", {})
    metadata = llm_result.get("metadata")

    # Assign agent types to each sub-task
    for task in sub_tasks:
        task["agent_type"] = assign_agent(task)

    return TaskPlan(
        goal=goal,
        sub_tasks=sub_tasks,
        dependency_graph=dependency_graph,
        metadata=metadata,
    )


async def create_tasks_from_plan(db: AsyncSession, plan: TaskPlan) -> list:
    """Persist a TaskPlan to the database, creating Task records.

    Args:
        db: Database session.
        plan: The TaskPlan to persist.

    Returns:
        List of created Task ORM objects with their generated IDs.
    """
    created_tasks = []
    # Sub-tasks may come with a suggested order; create in dependency order
    for sub_task in plan.sub_tasks:
        task = await create_task(
            db=db,
            title=sub_task.get("title", "Unnamed task"),
            agent_type=sub_task.get("agent_type", "orchestrator"),
            description=sub_task.get("description"),
            priority=sub_task.get("priority", 3),
            source="supervisor",
        )
        # Store dependency info in metadata_json
        depends_on = sub_task.get("depends_on", [])
        if depends_on:
            task.metadata_json = {"depends_on": depends_on}

        created_tasks.append(task)

    await db.flush()
    return created_tasks
