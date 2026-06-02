"""HITL Interrupt API — human review queue for agent decisions.

Public endpoints (no auth needed for HQ proxy access):
- GET  /interrupts/pending        — list pending interrupts
- GET  /interrupts                — list all (with filters)
- GET  /interrupts/{id}           — single interrupt detail
- POST /interrupts/{id}/approve   — approve → return context
- POST /interrupts/{id}/reject    — reject with reason
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core import interrupt_service

router = APIRouter(tags=["interrupts"])


class RejectRequest(BaseModel):
    reason: str


class CreateRequest(BaseModel):
    agent_type: str
    task_id: int
    reason: str
    context: dict | None = None


@router.get("/interrupts/pending")
async def pending_interrupts():
    """Return all interrupts with status=pending."""
    return {"interrupts": interrupt_service.get_pending_interrupts()}


@router.get("/interrupts")
async def list_interrupts(status: str | None = None, agent_type: str | None = None, limit: int = 50):
    """List all interrupts with optional filters."""
    return {"interrupts": interrupt_service.list_all(status, agent_type, limit)}


@router.get("/interrupts/{interrupt_id}")
async def get_interrupt(interrupt_id: int):
    """Get a single interrupt by ID."""
    result = interrupt_service.get_interrupt(interrupt_id)
    if not result:
        raise HTTPException(404, f"Interrupt {interrupt_id} not found")
    return result


@router.post("/interrupts/{interrupt_id}/approve")
async def approve_interrupt(interrupt_id: int):
    """Approve a pending interrupt. Returns the context for agent resumption."""
    context = interrupt_service.approve_interrupt(interrupt_id)
    if context is None:
        raise HTTPException(404, f"Interrupt {interrupt_id} not found or already decided")
    return {"status": "approved", "context": context}


@router.post("/interrupts/{interrupt_id}/reject")
async def reject_interrupt(interrupt_id: int, body: RejectRequest):
    """Reject a pending interrupt with a reason."""
    ok = interrupt_service.reject_interrupt(interrupt_id, body.reason)
    if not ok:
        raise HTTPException(404, f"Interrupt {interrupt_id} not found or already decided")
    return {"status": "rejected", "reason": body.reason}


@router.post("/interrupts")
async def create_interrupt(body: CreateRequest):
    """Create a new interrupt (used internally by agents)."""
    iid = interrupt_service.create_interrupt(
        agent_type=body.agent_type,
        task_id=body.task_id,
        reason=body.reason,
        context=body.context,
    )
    return {"interrupt_id": iid, "status": "pending"}
