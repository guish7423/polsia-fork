"""Sandbox testing bed API — manage pending actions and safety rules."""

from fastapi import APIRouter, HTTPException

from app.services.sandbox_service import (
    approve_action,
    cleanup_expired,
    get_pending_action,
    get_pending_actions,
    get_sandbox_summary,
    reject_action,
)

router = APIRouter(prefix="/sandbox", tags=["sandbox"])


@router.get("/summary")
async def sandbox_summary():
    """Get sandbox stats."""
    return get_sandbox_summary()


@router.get("/pending")
async def list_pending(status: str | None = None):
    """List pending actions, optionally filtered by status."""
    return get_pending_actions(status=status)


@router.get("/pending/{action_id}")
async def get_action(action_id: int):
    """Get a single pending action."""
    action = get_pending_action(action_id)
    if not action:
        raise HTTPException(404, "Action not found")
    return action


@router.post("/pending/{action_id}/approve")
async def approve(action_id: int, reviewer: str = "hq"):
    """Approve a pending action."""
    result = approve_action(action_id, reviewer=reviewer)
    if not result:
        raise HTTPException(404, "Action not found")
    return {"status": "approved", "action": result}


@router.post("/pending/{action_id}/reject")
async def reject(action_id: int, reason: str = "", reviewer: str = "hq"):
    """Reject a pending action."""
    result = reject_action(action_id, reason=reason, reviewer=reviewer)
    if not result:
        raise HTTPException(404, "Action not found")
    return {"status": "rejected", "action": result}


@router.post("/cleanup")
async def cleanup(hours: int = 72):
    """Clean up expired pending actions."""
    count = cleanup_expired(hours=hours)
    return {"cleaned": count}
