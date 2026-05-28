"""Celery tasks for daily orchestration cycles."""

import asyncio
from datetime import date

try:
    from celery import shared_task
except ImportError:
    # Celery not available — stub for test compatibility
    def shared_task(*args, **kwargs):
        def decorator(f):
            f.delay = lambda *a, **kw: None
            return f
        return decorator(args[0]) if args and callable(args[0]) else decorator

from app.core.database import async_session
from app.agents import agent_map
from app.services.report_service import get_or_create_report


@shared_task(bind=True)
def run_morning_cycle(self):
    """Morning orchestration: plan the day, review strategy, research competitors."""
    async def _run():
        async with async_session() as db:
            # 1. Orchestrator — creates daily plan + tasks
            orchestrator_cls = agent_map.get("orchestrator")
            if orchestrator_cls:
                orchestrator = orchestrator_cls()
                await orchestrator.run(db)

            # 2. BusinessPlanning — strategy review
            bp_cls = agent_map.get("business_planning")
            if bp_cls:
                bp = bp_cls()
                await bp.run(db)

            # 3. CompetitorResearch — market scan
            cr_cls = agent_map.get("competitor_research")
            if cr_cls:
                cr = cr_cls()
                await cr.run(db)

            await db.commit()

    return asyncio.run(_run())


@shared_task(bind=True)
def run_evening_cycle(self):
    """Evening cycle: finance snapshot + daily report."""
    async def _run():
        async with async_session() as db:
            # 1. Finance — revenue snapshot + expenses
            finance_cls = agent_map.get("finance")
            if finance_cls:
                finance = finance_cls()
                await finance.run(db)

            # 2. Update daily report with evening summary
            report = await get_or_create_report(db, date.today())
            report.evening_summary = "Evening cycle complete"
            await db.commit()

    return asyncio.run(_run())
