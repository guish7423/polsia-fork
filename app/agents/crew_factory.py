"""Crew factory — maps agent types to agent classes and dispatches tasks."""
import asyncio

from app.agents import agent_map
from app.core.database import async_session


async def run_agent_for_task(
    agent_type: str, task: dict, context: dict | None = None
) -> dict:
    """Run an agent for a given task async. Returns summary dict.

    Args:
        agent_type: Type of agent to run (e.g. "social_media").
        task: Task dict with title, description, etc.
        context: Optional company context dict.

    Returns:
        Dict with summary of what the agent did.

    Raises:
        ValueError: If agent_type is unknown.
    """
    agent_cls = agent_map.get(agent_type)
    if not agent_cls:
        raise ValueError(f"Unknown agent type: {agent_type}")

    agent = agent_cls()
    async with async_session() as db:
        result = await agent.run(db, {"task": task, **(context or {})})
        await db.commit()
        return result


def run_agent_for_task_sync(
    agent_type: str, task: dict, context: dict | None = None
) -> dict:
    """Sync wrapper for run_agent_for_task (for Celery compatibility)."""
    return asyncio.run(run_agent_for_task(agent_type, task, context))
