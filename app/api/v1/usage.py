"""LLM usage/cost tracking API routes."""
from fastapi import APIRouter, Depends

from app.core.auth import verify_api_key
from app.agents.base import llm_usage

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("/costs")
async def get_llm_costs(_: str = Depends(verify_api_key)):
    """Return LLM usage statistics and cost breakdown."""
    summary = llm_usage.summary()
    return {
        **summary,
        "history": llm_usage.history[-50:],  # Last 50 calls
    }
