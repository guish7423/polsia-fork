"""Agent API routes — monitor, runs, trigger, and SSE streaming."""

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db
from app.services.task_service import VALID_AGENT_TYPES
from app.services.activity_service import log_activity

router = APIRouter(tags=["agents"])


# ─── Monitor ──────────────────────────────────────────────────────────────────


@router.get("/agents/monitor")
async def agent_monitor(db: AsyncSession = Depends(get_db)):
    """Real-time agent monitor: status, latest run, today's stats per agent."""
    from app.services.agent_monitor_service import get_agent_monitor
    return await get_agent_monitor(db)


# ─── Agent Runs ───────────────────────────────────────────────────────────────


@router.get("/agents/runs")
async def list_agent_runs(
    agent_type: str | None = Query(None, description="Filter by agent type"),
    status: str | None = Query(None, description="Filter by run status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List agent runs with optional filters and pagination."""
    from app.services.agent_monitor_service import get_agent_runs
    runs, total = await get_agent_runs(
        db, agent_type=agent_type, status=status, limit=limit, offset=offset,
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "runs": [
            {
                "id": r.id,
                "agent_type": r.agent_type,
                "run_type": r.run_type,
                "status": r.status,
                "tokens_used": r.tokens_used,
                "cost_usd": r.cost_usd,
                "duration_secs": r.duration_secs,
                "llm_call_count": r.llm_call_count,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "ended_at": r.ended_at.isoformat() if r.ended_at else None,
            }
            for r in runs
        ],
    }


@router.get("/agents/runs/{run_id}")
async def get_agent_run_detail(
    run_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Detailed view of a single agent run with LLM call data."""
    from app.services.agent_monitor_service import get_agent_run_detail
    detail = await get_agent_run_detail(db, run_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return detail


@router.get("/agents/runs/stats/summary")
async def agent_run_stats(
    days: int = Query(7, ge=1, le=90),
    agent_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Aggregated agent run statistics for the last N days."""
    from app.services.agent_monitor_service import get_agent_run_stats
    return await get_agent_run_stats(db, agent_type=agent_type, days=days)


# ─── Legacy: Trigger ──────────────────────────────────────────────────────────


@router.get("/agents")
async def list_agents(db: AsyncSession = Depends(get_db)):
    """List all agents — delegates to /agents/monitor."""
    from app.services.agent_monitor_service import get_agent_monitor
    return await get_agent_monitor(db)


@router.post("/agents/{agent_type}/trigger")
async def trigger_agent(
    agent_type: str,
    db: AsyncSession = Depends(get_db),
):
    """Trigger an agent run (records activity, actual execution via Celery).

    Sandbox gate: checks safety rules before allowing execution.
    """
    if agent_type not in VALID_AGENT_TYPES:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {agent_type}")

    from app.agents.base import sandbox_verdict, submit_sandbox_action

    # ── Sandbox gate ──────────────────────────────────────────────────────
    verdict = sandbox_verdict(agent_type)
    if verdict["verdict"] == "block":
        raise HTTPException(
            status_code=403,
            detail={
                "message": verdict.get("message", "Blocked by sandbox"),
                "rule_id": verdict.get("rule_id"),
                "verdict": "block",
            },
        )
    if verdict["verdict"] == "pending":
        record = submit_sandbox_action(agent_type, summary=f"Manual trigger: {agent_type}")
        return {
            "message": f"{agent_type} agent queued for human approval",
            "pending_id": record.get("id"),
            "verdict": "pending",
        }

    await log_activity(
        db, agent_type=agent_type, action="triggered",
        summary=f"{agent_type} agent triggered manually",
    )

    # Dispatch Celery task for actual execution
    from celery_app.tasks.agent_tasks import run_agent as celery_run_agent
    celery_run_agent.delay(agent_type)

    return {"message": f"{agent_type} agent triggered", "verdict": "allow"}


# ─── Agent SSE Stream ─────────────────────────────────────────────────────────


@router.get("/agents/{agent_type}/stream")
async def stream_agent_steps(agent_type: str):
    """SSE endpoint: streams agent step events in real-time.

    Returns a ``text/event-stream`` response.  The client receives all
    buffered steps first, then live events as they are published.
    Disconnected clients are cleaned up automatically.

    SSE format::

        event: step
        data: {"step":"thinking","content":"Analyzing...","ts":"..."}
    """
    if not settings.agent_streaming_enabled:
        raise HTTPException(
            status_code=404,
            detail="Agent streaming is disabled",
        )

    from app.core.agent_stream import AgentStreamManager

    manager = AgentStreamManager.get_instance()

    async def _event_stream():
        try:
            async for step in manager.stream_steps(agent_type):
                yield f"event: step\ndata: {json.dumps(step)}\n\n"
        except asyncio.CancelledError:
            pass  # client disconnected — clean exit

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )



