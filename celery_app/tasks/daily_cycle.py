"""Celery tasks for daily orchestration cycles.

Morning cycle (6am UTC): Orchestrator plans the day + strategy agents run.
Evening cycle (10pm UTC): Finance snapshot + report generation + summary.
"""
import asyncio
import logging
from datetime import date

try:
    from celery import shared_task
except ImportError:
    def shared_task(*args, **kwargs):
        def decorator(f):
            f.delay = lambda *a, **kw: None
            return f
        return decorator(args[0]) if args and callable(args[0]) else decorator

from app.core.database import async_session
from app.agents import agent_map
from app.services.report_service import get_or_create_report
from app.services.activity_service import log_activity

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def run_morning_cycle(self):
    """Morning orchestration: plan the day, review strategy, research competitors."""
    async def _run():
        async with async_session() as db:
            try:
                # 1. Orchestrator — creates daily plan + tasks
                orchestrator_cls = agent_map.get("orchestrator")
                if orchestrator_cls:
                    orchestrator = orchestrator_cls()
                    await orchestrator.run(db, {"cycle": "morning"})
                    logger.info("Morning cycle: orchestrator completed")

                # 2. BusinessPlanning — strategy review
                bp_cls = agent_map.get("business_planning")
                if bp_cls:
                    bp = bp_cls()
                    await bp.run(db, {"cycle": "morning"})

                # 3. CompetitorResearch — market scan
                cr_cls = agent_map.get("competitor_research")
                if cr_cls:
                    cr = cr_cls()
                    await cr.run(db, {"cycle": "morning"})

                await db.commit()
                logger.info("Morning cycle complete")
                return {"status": "ok", "phase": "morning"}
            except Exception as e:
                await db.rollback()
                logger.error(f"Morning cycle failed: {e}")
                raise

    return asyncio.run(_run())


@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def run_evening_cycle(self):
    """Evening cycle: finance snapshot + daily report + executive summary."""
    async def _run():
        async with async_session() as db:
            try:
                today = date.today()

                # 1. Finance — revenue snapshot + expenses
                finance_cls = agent_map.get("finance")
                if finance_cls:
                    finance = finance_cls()
                    await finance.run(db, {"cycle": "evening"})

                # 2. Update daily report with evening summary
                report = await get_or_create_report(db, today)
                report.evening_summary = "Evening cycle complete"

                # 3. Log activity
                await log_activity(
                    db, agent_type="orchestrator", action="evening_cycle",
                    summary=f"Evening cycle completed for {today.isoformat()}",
                )

                await db.commit()
                logger.info(f"Evening cycle complete for {today}")
                return {"status": "ok", "phase": "evening", "date": today.isoformat()}
            except Exception as e:
                await db.rollback()
                logger.error(f"Evening cycle failed: {e}")
                raise

    return asyncio.run(_run())
