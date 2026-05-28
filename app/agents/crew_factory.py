"""Crew factory — maps agent types to agent classes and dispatches tasks."""

from app.agents import agent_map


def run_agent_for_task(agent_type: str, task: dict, context: dict | None = None) -> dict:
    """Run an agent for a given task. Returns summary dict.

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

    # Create instance and run (sync dispatch)
    agent = agent_cls()
    result = agent.run_sync(task, context)
    return result
