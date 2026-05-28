"""Agent API routes — status, trigger, and execution dispatch."""

import uuid
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import verify_api_key
from app.core.database import get_db
from app.services.task_service import VALID_AGENT_TYPES
from app.services.activity_service import log_activity

router = APIRouter(tags=["agents"])

AGENT_DESCRIPTIONS = {
    "orchestrator": "Daily planning and agent coordination",
    "business_planning": "Strategic planning and KPI refinement",
    "competitor_research": "Competitive analysis and market research",
    "social_media": "Social media content creation and publishing",
    "email_outreach": "Customer prospecting and email marketing",
    "customer_support": "Automated customer inquiry responses",
    "ads_management": "Ad campaign optimization and budget allocation",
    "code_generation": "Code writing for company product",
    "finance": "Financial tracking and revenue reporting",
    "deployment": "Deployment lifecycle management",
}


@router.get("/agents/status")
async def list_agents(api_key: str = Depends(verify_api_key)):
    """List all agents with their current status."""
    return [
        {
            "agent_type": at,
            "name": at.replace("_", " ").title(),
            "description": AGENT_DESCRIPTIONS.get(at, ""),
            "status": "idle",
            "last_run": None,
        }
        for at in VALID_AGENT_TYPES
    ]


@router.get("/agents")
async def get_agents(api_key: str = Depends(verify_api_key)):
    """Alias for /agents/status."""
    return await list_agents(api_key)


async def _run_agent_background(agent_type: str, task_id: str):
    """Run agent in background when Celery is not available."""
    from app.agents import agent_map
    from app.core.database import async_session

    agent_class = agent_map.get(agent_type)
    if not agent_class:
        return

    async with async_session() as db:
        agent = agent_class()
        await agent.run(db, {"source": "api", "task_id": task_id})
        await db.commit()


@router.post("/agents/{agent_type}/trigger", status_code=202)
async def trigger_agent(
    agent_type: str,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Trigger an agent run. Dispatches to Celery if available, otherwise runs background."""
    if agent_type not in VALID_AGENT_TYPES:
        raise HTTPException(status_code=422, detail=f"Unknown agent: {agent_type}")

    task_id = str(uuid.uuid4())

    # Log trigger activity
    await log_activity(
        db, agent_type=agent_type, action="triggered",
        summary=f"{agent_type} agent triggered manually",
    )

    # Try Celery dispatch first
    try:
        from celery_app.tasks.agent_tasks import run_agent_task
        run_agent_task.delay(agent_type, {"source": "api", "task_id": task_id})
    except Exception:
        # Celery not available — run in FastAPI background task
        background_tasks.add_task(_run_agent_background, agent_type, task_id)

    return {"status": "queued", "task_id": task_id}
