"""Agent API routes — status and trigger."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

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


@router.get("/agents")
async def list_agents():
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


@router.post("/agents/{agent_type}/trigger")
async def trigger_agent(
    agent_type: str,
    db: AsyncSession = Depends(get_db),
):
    """Trigger an agent run (records activity, actual execution via Celery)."""
    if agent_type not in VALID_AGENT_TYPES:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {agent_type}")

    await log_activity(
        db, agent_type=agent_type, action="triggered",
        summary=f"{agent_type} agent triggered manually",
    )

    return {"message": f"{agent_type} agent triggered"}
    return {"message": f"{agent_type} agent triggered (mock)"}
