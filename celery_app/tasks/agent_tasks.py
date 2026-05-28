"""Celery tasks for dispatching agents."""
import asyncio

try:
    from celery import shared_task
except ImportError:
    # Celery not available — stub for test compatibility
    def shared_task(*args, **kwargs):
        def decorator(f):
            f.delay = lambda *a, **kw: None
            return f
        return decorator(args[0]) if args and callable(args[0]) else decorator


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def run_agent(self, agent_type: str, context: dict | None = None) -> dict:
    """Run any registered agent by type. Generic dispatcher for Celery Beat."""
    from app.core.database import async_session
    from app.agents import agent_map

    agent_class = agent_map.get(agent_type)
    if not agent_class:
        raise ValueError(f"Unknown agent type: {agent_type}")

    async def _run():
        async with async_session() as db:
            agent = agent_class()
            return await agent.run(db, context)

    try:
        result = asyncio.run(_run())
        return result
    except Exception as exc:
        self.retry(exc=exc)


run_agent_task = run_agent  # Alias for test compatibility
