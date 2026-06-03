"""Celery tasks for dispatching agents — with AgentRun lifecycle tracking."""

import asyncio
import json
import time

from celery import shared_task

from app.services.weekly_report_service import generate_and_email_report


def _build_span(span_type: str, started_at: float, detail: dict | None = None) -> dict:
    """Build a structured execution span entry."""
    return {
        "span_type": span_type,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started_at)),
        "duration_ms": int((time.monotonic() - started_at) * 1000),
        "detail": detail or {},
    }


def _record_spans(spans: list[dict]) -> dict:
    """Wrap execution spans in a dict for JSON column compatibility."""
    return {"spans": spans}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def run_agent(self, agent_type: str, context: dict | None = None, task_id: int | None = None) -> dict:
    """Run any registered agent by type — with AgentRun lifecycle tracking.

    Creates an AgentRun record at start, updates it on completion/error,
    tracks execution_spans, and broadcasts activity via WebSocket.
    """
    from app.agents import agent_map
    from app.agents.base import sandbox_verdict, submit_sandbox_action

    agent_class = agent_map.get(agent_type)
    if not agent_class:
        raise ValueError(f"Unknown agent type: {agent_type}")

    # ── Sandbox gate ──────────────────────────────────────────────────────
    verdict = sandbox_verdict(agent_type)
    if verdict["verdict"] == "block":
        return {
            "result": "sandbox_blocked",
            "agent_type": agent_type,
            "rule_id": verdict.get("rule_id"),
            "message": verdict.get("message", "Blocked by sandbox"),
        }
    if verdict["verdict"] == "pending":
        record = submit_sandbox_action(agent_type)
        return {
            "result": "sandbox_pending",
            "agent_type": agent_type,
            "pending_id": record.get("id"),
            "rule_id": verdict.get("rule_id"),
            "message": verdict.get("message", "Queued for human approval"),
        }

    # ── Execute with AgentRun tracking ────────────────────────────────────
    from app.core.database import async_session

    task_start_wall = time.time()
    task_start_mono = time.monotonic()
    spans: list[dict] = []

    async def _run():
        from app.models.agent_run import AgentRun
        from app.core.events import publish_activity

        async with async_session() as db:
            agent = agent_class()

            # 1️⃣ Create AgentRun record
            run = AgentRun(
                task_id=task_id,
                agent_type=agent_type,
                run_type="task",
                status="running",
                input_context=context or {},
                started_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            )
            db.add(run)
            await db.flush()
            run_id: int = run.id  # type: ignore[assignment]

            # Broadcast "started" event
            try:
                await publish_activity(
                    agent_type=agent_type,
                    action="started",
                    summary=f"{agent_type} agent started (run #{run_id})",
                    level="info",
                    run_id=run_id,
                )
            except Exception:
                pass

            spans.append(_build_span("state_transition", task_start_mono, {"from": None, "to": "running"}))

            try:
                # 2️⃣ Execute agent
                span_start = time.monotonic()
                result = await agent.run(db, context)
                spans.append(_build_span("state_transition", span_start, {
                    "from": "running",
                    "to": "completed" if result.get("status") != "interrupt" else "interrupt",
                }))

                # 3️⃣ Handle HITL interrupt
                if isinstance(result, dict) and result.get("status") == "interrupt":
                    run.status = "interrupt"
                    run.output = result
                    run.ended_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
                    run.duration_secs = time.monotonic() - task_start_mono
                    run.execution_spans = _record_spans(spans)
                    await db.commit()

                    try:
                        await publish_activity(
                            agent_type=agent_type,
                            action="interrupt",
                            summary=f"{agent_type} paused — awaiting human approval (run #{run_id})",
                            level="warning",
                            run_id=run_id,
                        )
                    except Exception:
                        pass

                    return result

                # 4️⃣ Update run on success
                run.status = "completed"
                run.output = result
                run.ended_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
                run.duration_secs = time.monotonic() - task_start_mono
                run.execution_spans = _record_spans(spans)
                await db.commit()

                # Broadcast "completed" event
                try:
                    await publish_activity(
                        agent_type=agent_type,
                        action="completed",
                        summary=f"{agent_type} completed in {run.duration_secs:.1f}s (run #{run_id})",
                        level="info",
                        run_id=run_id,
                        metadata={
                            "duration_secs": run.duration_secs,
                            "cost_usd": run.cost_usd,
                            "status": "completed",
                        },
                    )
                except Exception:
                    pass

                return result

            except Exception as exc:
                # 5️⃣ Update run on failure
                spans.append(_build_span("state_transition", task_start_mono, {
                    "from": "running",
                    "to": "error",
                    "error": str(exc)[:500],
                }))
                run.status = "error"
                run.output = {"error": str(exc)}
                run.ended_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
                run.duration_secs = time.monotonic() - task_start_mono
                run.execution_spans = _record_spans(spans)
                await db.commit()

                try:
                    await publish_activity(
                        agent_type=agent_type,
                        action="error",
                        summary=f"{agent_type} failed: {str(exc)[:120]} (run #{run_id})",
                        level="error",
                        run_id=run_id,
                    )
                except Exception:
                    pass

                raise  # Let Celery retry handle this

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
def run_order_scan(self):
    """Scan: check external platforms for new orders, then evaluate."""
    from app.services.order_scanner_service import scan_platform
    from app.core.database import async_session
    from app.agents import agent_map
    from app.agents.order_scanner import OrderScannerAgent

    async def _full_pipeline():
        # 1. Scan all platforms for new orders
        platforms = ["upwork", "fiverr", "zhubajie"]
        total = 0
        for platform in platforms:
            async with async_session() as db:
                try:
                    orders = await scan_platform(db, platform)
                    await db.commit()
                    total += len(orders)
                except Exception as e:
                    print(f"[scan] {platform} error: {e}")
        # 2. Evaluate all scanned orders
        agent = OrderScannerAgent()
        async with async_session() as db:
            result = await agent.run(db)
            await db.commit()
            return {"scanned": total, "evaluation": result}

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_full_pipeline())
    finally:
        loop.close()


@shared_task(bind=True)
def run_order_fulfill(self):
    """Fulfill: process accepted orders."""
    return run_agent("order_fulfiller")


@shared_task(bind=True)
def run_deploy_sweep(self):
    """Deploy: plan and execute deployment orders."""
    return run_agent("deploy_agent")


@shared_task(bind=True)
def run_lead_nurture(self):
    """Nurture: follow up with new leads."""
    return run_agent("lead_nurturing")


@shared_task(bind=True)
def run_monitor_sweep(self):
    """Monitor: check all service health."""
    return run_agent("monitor")


@shared_task(bind=True)
def run_ads_stripe_sync(self):
    """Sync: collect ad metrics and run ads management."""
    return run_agent("ads_management")


@shared_task(bind=True)
def run_evolution_sweep(self):
    """Evolution: analyze agent performance and drive improvements."""
    return run_agent("evolution")


@shared_task(bind=True)
def run_briefing_sweep(self):
    """Intel: collect market intelligence daily briefing."""
    return run_agent("market_intel")


@shared_task(bind=True)
def run_sandbox_cleanup(self):
    """Sandbox: cleanup expired pending actions."""
    from app.services.sandbox_service import cleanup_expired
    count = cleanup_expired(hours=72)
    return {"cleaned": count, "task": "sandbox_cleanup"}


@shared_task(bind=True)
def run_proposal_nurture_sweep(self):
    """Nurture: scan sent-but-unread proposals and flag for follow-up."""
    from app.core.database import async_session
    from app.services.proposal_nurture_service import run_nurture_check

    async def _run():
        async with async_session() as db:
            result = await run_nurture_check(db)
            await db.commit()
            return result

    return asyncio.run(_run())


@shared_task(bind=True)
def run_weekly_report(self):
    """Generate and email weekly report (runs Monday 9:00)."""
    from app.core.database import async_session

    async def _run():
        async with async_session() as db:
            result = await generate_and_email_report(db)
            return result

    return asyncio.run(_run())
