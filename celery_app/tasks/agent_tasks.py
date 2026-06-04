"""Celery tasks for dispatching agents — with AgentRun lifecycle tracking."""

import asyncio
import json
import time

from celery import shared_task
from sqlalchemy import select, func

from app.services.weekly_report_service import generate_and_email_report

# ─── Consecutive failure tracker ───────────────────────────────────────────────

_consecutive_failures: dict[str, int] = {}

# ─── Scheduler-aware dispatch ────────────────────────────────────────────────


def dispatch_agent(agent_type: str, context: dict | None = None,
                   task_id: int | None = None, tenant_id: int = 0) -> dict:
    """Dispatch an agent through the scheduler, checking load first.

    When ``settings.scheduler_enabled`` is True, calls the scheduler to
    determine the appropriate Celery queue. Otherwise falls back to the
    standard ``run_agent.delay()`` path.

    For now, this is a thin wrapper that calls ``run_agent`` directly;
    future iterations will use ``apply_async(queue=...)`` for true
    queue-aware routing.
    """
    from app.config import settings

    if settings.scheduler_enabled and tenant_id > 0:
        _try_record_schedule(agent_type, tenant_id)

    return run_agent(agent_type, context=context, task_id=task_id)


def _try_record_schedule(agent_type: str, tenant_id: int) -> None:
    """Run the scheduler decision (fire-and-forget, failures are logged)."""
    import asyncio as _asyncio

    try:
        from app.core.database import async_session
        from app.services.agent_scheduler import AgentSchedulerService

        async def _do():
            async with async_session() as _db:
                return await AgentSchedulerService.schedule_agent(
                    _db, agent_type, tenant_id,
                )

        queue = _asyncio.run(_do())
        if queue == "low_priority":
            import logging
            logger = logging.getLogger(__name__)
            logger.info(
                "scheduler=[%s] tenant=%d agent=%s queue=%s",
                agent_type, tenant_id, agent_type, queue,
            )
    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            "scheduler: failed to record schedule for %s (tenant=%d)",
            agent_type, tenant_id, exc_info=True,
        )


def _prepare_context(context: dict | None) -> dict:
    """Prepare agent context (step function for checkpoint)."""
    return context or {}


async def _save_results(result: dict, task_id: int | None) -> dict:
    """Save agent results (step function for checkpoint)."""
    return result


def _build_span(span_type: str, started_at: float, detail: dict | None = None) -> dict:
    """Build a structured execution span entry."""
    return {
        "span_type": span_type,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started_at)),
        "duration_ms": int((time.monotonic() - started_at) * 1000),
        "detail": detail or {},
    }


def _record_spans(spans: list[dict]) -> dict | None:
    """Wrap execution spans in a dict for JSON column compatibility."""
    return {"spans": spans}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def run_agent(self, agent_type: str, context: dict | None = None, task_id: int | None = None) -> dict:
    """Run any registered agent by type — with AgentRun lifecycle tracking.

    Creates an AgentRun record at start, updates it on completion/error,
    tracks execution_spans, and broadcasts activity via WebSocket.

    When ``settings.durable_execution_enabled`` is True, uses checkpoint-based
    durable execution that persists step results and survives worker crashes.
    """
    from app.config import settings

    # ── Dispatch: durable execution path ──────────────────────────────────
    if settings.durable_execution_enabled:
        return asyncio.run(
            _run_agent_with_checkpoint(self, agent_type, context, task_id)
        )

    # ── Standard path ─────────────────────────────────────────────────────
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

    # ── Container-level sandbox (Docker isolation) ─────────────────────────
    from app.config import settings as _settings

    if _settings.sandbox_enabled:
        from app.core.database import async_session as _sandbox_session
        from app.services.sandbox_runtime import SandboxRuntime

        async def _sandbox_run():
            async with _sandbox_session() as db:
                runtime = SandboxRuntime(db=db, enabled=True)
                return await runtime.execute_in_sandbox(
                    agent_type=agent_type,
                    command=["python", "-m", "app.agents", agent_type],
                    agent_run_id=task_id,
                )

        try:
            return asyncio.run(_sandbox_run())
        except Exception as exc:
            self.retry(exc=exc)

    # ── Execute with AgentRun tracking ────────────────────────────────────
    from app.core.database import async_session

    task_start_wall = time.time()
    task_start_mono = time.monotonic()
    spans: list[dict] = []

    async def _run():
        from app.models.agent_run import AgentRun
        from app.models.task import Task
        from app.core.events import publish_activity
        from app.services.plugin_registry import call_hooks

        async with async_session() as db:
            agent = agent_class()

            # Resolve tenant_id from task if available
            _tenant_id: int = 0
            if task_id is not None:
                task_row = await db.get(Task, task_id)
                if task_row is not None:
                    _tenant_id = task_row.tenant_id

            # 0️⃣ Fire before_agent_run hook (fire-and-forget, timeout logged)
            try:
                await call_hooks(
                    db, tenant_id=_tenant_id, hook_name="before_agent_run",
                    context={"agent_type": agent_type, "task_id": task_id, "input_context": context},
                    timeout=3.0,
                )
            except Exception:
                pass  # Hook failure must never block agent execution

            # 1️⃣ Create AgentRun record
            run = AgentRun(
                task_id=task_id,
                agent_type=agent_type,
                tenant_id=_tenant_id,
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

            # 1️⃣b Scheduler gate (fire-and-forget, non-blocking)
            if _tenant_id > 0:
                try:
                    from app.config import settings as _sched_settings
                    if _sched_settings.scheduler_enabled:
                        from app.services.agent_scheduler import AgentSchedulerService
                        _queue = await AgentSchedulerService.schedule_agent(
                            db, agent_type, _tenant_id,
                        )
                        spans.append(_build_span(
                            "scheduler", task_start_mono,
                            {"queue": _queue, "tenant_id": _tenant_id},
                        ))
                except Exception:
                    pass  # Scheduler failure must never block agent execution

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

                # Fire after_agent_run hook (fire-and-forget)
                try:
                    await call_hooks(
                        db, tenant_id=0, hook_name="after_agent_run",
                        context={
                            "agent_type": agent_type,
                            "run_id": run_id,
                            "output": result,
                            "tokens_used": 0,
                            "cost_usd": run.cost_usd if hasattr(run, "cost_usd") else 0,
                        },
                        timeout=3.0,
                    )
                except Exception:
                    pass

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

                # ── Reset consecutive failure counter on success ───────────
                _consecutive_failures.pop(agent_type, None)

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

                # Fire on_agent_error hook (fire-and-forget)
                try:
                    await call_hooks(
                        db, tenant_id=0, hook_name="on_agent_error",
                        context={
                            "agent_type": agent_type,
                            "run_id": run_id,
                            "error_message": str(exc)[:500],
                        },
                        timeout=3.0,
                    )
                except Exception:
                    pass

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

                # ── Alert injection: 3 consecutive failures ───────────────
                _consecutive_failures[agent_type] = _consecutive_failures.get(agent_type, 0) + 1
                if _consecutive_failures[agent_type] >= 3:
                    _consecutive_failures[agent_type] = 0
                    try:
                        from app.services.alert_service import AlertService
                        await AlertService.from_agent_error(
                            db, tenant_id=_tenant_id,
                            source=f"agent:{agent_type}",
                            error_count=_consecutive_failures[agent_type],  # 0 after reset
                        )
                    except Exception:
                        pass

                raise  # Let Celery retry handle this

    try:
        result = asyncio.run(_run())
        return result
    except Exception as exc:
        self.retry(exc=exc)


async def _run_agent_with_checkpoint(
    self, agent_type: str, context: dict | None, task_id: int | None,
) -> dict:
    """Execute agent with checkpoint-based durable execution.

    Each step is checkpointed: on retry after crash, completed steps are
    skipped (results restored from DB).
    """
    from app.agents import agent_map
    from app.core.database import async_session
    from app.core.checkpoint import Checkpoint
    from app.models.agent_run import AgentRun
    from app.models.task import Task
    from app.services.plugin_registry import call_hooks

    agent_class = agent_map.get(agent_type)
    if not agent_class:
        raise ValueError(f"Unknown agent type: {agent_type}")

    async with async_session() as db:
        # 0️⃣ Resolve tenant_id from the task (if task_id is given)
        _cp_tenant_id: int = 0
        if task_id is not None:
            task = await db.get(Task, task_id)
            if task is not None and task.tenant_id is not None:
                _cp_tenant_id = task.tenant_id

        # 0️⃣ Fire before_agent_run hook
        try:
            await call_hooks(
                db, tenant_id=_cp_tenant_id, hook_name="before_agent_run",
                context={"agent_type": agent_type, "task_id": task_id, "input_context": context},
                timeout=3.0,
            )
        except Exception:
            pass

        # 1️⃣ Create AgentRun record
        run = AgentRun(
            task_id=task_id,
            agent_type=agent_type,
            tenant_id=_cp_tenant_id,
            run_type="task",
            status="running",
            input_context=context or {},
            durable_execution=True,
            started_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        )
        db.add(run)
        await db.flush()
        run_id: int = run.id  # type: ignore[assignment]

        # 2️⃣ Restore or create checkpoint
        if self.request.retries > 0:
            cp = await Checkpoint.restore_from_db(db, run_id, ttl=3600)
            if cp is None:
                cp = Checkpoint(f"run:{run_id}", ttl=3600)
        else:
            cp = Checkpoint(f"run:{run_id}", ttl=3600)

        try:
            # 3️⃣ Execute steps with checkpoint
            agent = agent_class()

            ctx = await cp.run("prepare", _prepare_context, context)
            result = await cp.run("execute", agent.run, db, ctx)
            await cp.run("save", _save_results, result, task_id)

            # 4️⃣ Persist checkpoint to DB
            await cp.save_to_db(db, run_id)

            # 4️⃣b Fire after_agent_run hook
            try:
                await call_hooks(
                    db, tenant_id=_cp_tenant_id, hook_name="after_agent_run",
                    context={
                        "agent_type": agent_type,
                        "run_id": run_id,
                        "output": result,
                        "tokens_used": 0,
                        "cost_usd": 0,
                    },
                    timeout=3.0,
                )
            except Exception:
                pass

            # 5️⃣ Update run on success
            # ── Reset consecutive failure counter on success ───────────────
            _consecutive_failures.pop(agent_type, None)
            run.status = "completed"
            run.output = result
            run.ended_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
            await db.commit()

            return result

        except Exception as exc:
            # ── Alert injection: 3 consecutive failures ───────────────────
            _consecutive_failures[agent_type] = _consecutive_failures.get(agent_type, 0) + 1
            if _consecutive_failures[agent_type] >= 3:
                _consecutive_failures[agent_type] = 0
                try:
                    from app.services.alert_service import AlertService
                    await AlertService.from_agent_error(
                        db, tenant_id=_cp_tenant_id,
                        source=f"agent:{agent_type}",
                        error_count=3,
                    )
                except Exception:
                    pass

            # 5️⃣b Fire on_agent_error hook
            try:
                await call_hooks(
                    db, tenant_id=_cp_tenant_id, hook_name="on_agent_error",
                    context={
                        "agent_type": agent_type,
                        "run_id": run_id,
                        "error_message": str(exc)[:500],
                    },
                    timeout=3.0,
                )
            except Exception:
                pass

            # 6️⃣ Persist partial progress before re-raising
            try:
                await cp.save_to_db(db, run_id)
            except Exception:
                pass
            run.status = "error"
            run.output = {"error": str(exc)}
            run.ended_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
            await db.commit()
            raise  # Let Celery retry handle this


@shared_task(bind=True)
def run_social_sweep(self):
    """Sweep: check social mentions and create content."""
    return dispatch_agent("social_media")


@shared_task(bind=True)
def run_email_sweep(self):
    """Sweep: process email outreach."""
    return dispatch_agent("email_outreach")


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
    return dispatch_agent("order_fulfiller")


@shared_task(bind=True)
def run_deploy_sweep(self):
    """Deploy: plan and execute deployment orders."""
    return dispatch_agent("deploy_agent")


@shared_task(bind=True)
def run_lead_nurture(self):
    """Nurture: follow up with new leads."""
    return dispatch_agent("lead_nurturing")


@shared_task(bind=True)
def run_monitor_sweep(self):
    """Monitor: check all service health."""
    return dispatch_agent("monitor")


@shared_task(bind=True)
def run_ads_stripe_sync(self):
    """Sync: collect ad metrics and run ads management."""
    return dispatch_agent("ads_management")


@shared_task(bind=True)
def run_evolution_sweep(self):
    """Evolution: analyze agent performance and drive improvements."""
    return dispatch_agent("evolution")


@shared_task(bind=True)
def run_briefing_sweep(self):
    """Intel: collect market intelligence daily briefing."""
    return dispatch_agent("market_intel")


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
