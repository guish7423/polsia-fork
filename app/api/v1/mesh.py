"""Mesh API — REST interface for inter-agent message inspection and posting."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.tenant_context import get_current_tenant
from app.services import mesh_bus

router = APIRouter(tags=["mesh"])


@router.get("/mesh/messages")
async def list_messages(
    agent_type: str | None = Query(None, description="Filter by recipient agent type"),
    status: str | None = Query(None, description="Filter by status: pending, delivered, read, failed"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List mesh messages, optionally filtered by agent type and status."""
    tenant = get_current_tenant()
    tenant_id = tenant.id if tenant else 1  # NOTE: silent fallback to 1 — log warning if missing for security audit

    if agent_type:
        messages = await mesh_bus.get_messages_for_agent(
            db, tenant_id, agent_type, status=status, limit=limit,
        )
    else:
        # Return all messages for this tenant
        from app.models.agent_message import AgentMessage
        from sqlalchemy import select

        conditions = [AgentMessage.tenant_id == tenant_id]
        if status:
            conditions.append(AgentMessage.status == status)
        result = await db.execute(
            select(AgentMessage).where(*conditions).order_by(
                AgentMessage.created_at.desc()
            ).limit(limit)
        )
        messages = list(result.scalars().all())

    return {
        "messages": [
            {
                "id": m.id,
                "sender_type": m.sender_type,
                "recipient_type": m.recipient_type,
                "message_type": m.message_type,
                "title": m.title,
                "body": m.body,
                "priority": m.priority,
                "status": m.status,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "delivered_at": m.delivered_at.isoformat() if m.delivered_at else None,
                "read_at": m.read_at.isoformat() if m.read_at else None,
            }
            for m in messages
        ],
        "total": len(messages),
    }


@router.get("/mesh/messages/{message_id}")
async def get_message(
    message_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a single mesh message by ID."""
    from app.models.agent_message import AgentMessage
    from sqlalchemy import select

    tenant = get_current_tenant()
    tenant_id = tenant.id if tenant else 1

    result = await db.execute(
        select(AgentMessage).where(
            AgentMessage.id == message_id,
            AgentMessage.tenant_id == tenant_id,
        )
    )
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    return {
        "id": msg.id,
        "sender_type": msg.sender_type,
        "recipient_type": msg.recipient_type,
        "message_type": msg.message_type,
        "title": msg.title,
        "body": msg.body,
        "priority": msg.priority,
        "status": msg.status,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
        "delivered_at": msg.delivered_at.isoformat() if msg.delivered_at else None,
        "read_at": msg.read_at.isoformat() if msg.read_at else None,
    }


@router.post("/mesh/messages", status_code=201)
async def send_mesh_message(
    sender_type: str = Query(..., description="Agent type sending the message"),
    recipient_type: str | None = Query(None, description="Target agent type (None=broadcast)"),
    message_type: str = Query("generic", description="Message type: generic, delegation, broadcast"),
    title: str = Query(..., description="Message title"),
    priority: int = Query(3, ge=1, le=5),
    body: dict | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Send a message through the agent mesh via API."""
    tenant = get_current_tenant()
    tenant_id = tenant.id if tenant else 1

    msg = await mesh_bus.send_message(
        db=db,
        tenant_id=tenant_id,
        sender_type=sender_type,
        recipient_type=recipient_type,
        message_type=message_type,
        title=title,
        body=body or {},
        priority=priority,
    )
    return {
        "message_id": msg.id,
        "status": "sent",
    }


@router.post("/mesh/messages/{message_id}/deliver")
async def mark_message_delivered(
    message_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Mark a mesh message as delivered."""
    tenant = get_current_tenant()
    tenant_id = tenant.id if tenant else 1

    msg = await mesh_bus.mark_delivered(db, message_id, tenant_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found or already delivered")
    return {"status": "delivered", "message_id": message_id}


@router.post("/mesh/messages/{message_id}/read")
async def mark_message_read(
    message_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Mark a mesh message as read."""
    tenant = get_current_tenant()
    tenant_id = tenant.id if tenant else 1

    msg = await mesh_bus.mark_read(db, message_id, tenant_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"status": "read", "message_id": message_id}


@router.get("/mesh/capabilities")
async def list_capabilities(
    capability: str | None = Query(None, description="Filter by capability name"),
):
    """List all registered agent capabilities."""
    from app.services.capability_registry import (
        all_capabilities,
        find_agents_by_capability,
    )

    if capability:
        matches = find_agents_by_capability(capability)
        return {
            "capability": capability,
            "agents": matches,
        }

    caps = all_capabilities()
    return {"capabilities": caps}


@router.get("/mesh/pending")
async def get_pending_messages(
    agent_type: str = Query(..., description="Agent type to fetch pending messages for"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get all pending mesh messages for a specific agent type."""
    tenant = get_current_tenant()
    tenant_id = tenant.id if tenant else 1

    messages = await mesh_bus.get_pending_messages(
        db, tenant_id, agent_type, limit=limit,
    )
    return {
        "agent_type": agent_type,
        "messages": [
            {
                "id": m.id,
                "sender_type": m.sender_type,
                "message_type": m.message_type,
                "title": m.title,
                "priority": m.priority,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
        "total": len(messages),
    }
