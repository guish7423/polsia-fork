"""Celery tasks for dispatching agents."""

import asyncio

from celery import shared_task


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


@shared_task(bind=True)
def run_social_sweep(self):
    """Sweep: check social mentions and create content."""
    return run_agent("social_media")


@shared_task(bind=True)
def run_email_sweep(self):
    """Sweep: process email outreach."""
    return run_agent("email_outreach")


@shared_task(bind=True)
def run_ads_stripe_sync(self):
    """Sync: collect ad metrics and run ads management."""
    return run_agent("ads_management")
