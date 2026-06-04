"""Agent Mesh Bus — inter-agent message routing, delivery, and Redis pub/sub."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_message import AgentMessage
from app.services.capability_registry import find_agents_by_capability

logger = logging.getLogger(__name__)

# ─── Redis Channel ──────────────────────────────────────────────────────────

MESH_CHANNEL = "agent:mesh"


async def _publish_to_redis(message: AgentMessage) -> None:
    """Publish a message notification to Redis for real-time delivery."""
    try:
        from app.core.redis_client import get_redis

        redis = await get_redis()
        if redis is None:
            return  # Redis not configured, DB-only delivery
        payload = {
            "type": "mesh_message",
            "message_id": message.id,
            "sender": message.sender_type,
            "recipient": message.recipient_type,
            "message_type": message.message_type,
            "title": message.title,
            "priority": message.priority,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        await redis.publish(MESH_CHANNEL, json.dumps(payload, default=str))
    except (ConnectionError, TimeoutError, OSError) as exc:
        logger.warning("Mesh Redis connection failed: %s", exc)


# ─── Send ───────────────────────────────────────────────────────────────────


async def send_message(
    db: AsyncSession,
    tenant_id: int,
    sender_type: str,
    message_type: str,
    title: str,
    *,
    recipient_type: str | None = None,
    body: dict | None = None,
    priority: int = 3,
    target_message_id: int | None = None,
    ttl_seconds: int = 86400,
) -> AgentMessage:
    """Send a message through the agent mesh.

    Args:
        db: Database session.
        tenant_id: Tenant scope.
        sender_type: Agent type sending the message.
        message_type: 'generic', 'delegation', 'broadcast', 'capability_query', 'result'.
        title: Short message title.
        recipient_type: Target agent type. None = broadcast to all.
        body: JSON-serializable payload.
        priority: 1-5 priority.
        target_message_id: For replies, the original message ID.
        ttl_seconds: Message expiry.

    Returns:
        The created AgentMessage.

    Raises:
        ValueError: If recipient_type is None and no capabilities searched.
    """
    msg = AgentMessage(
        tenant_id=tenant_id,
        sender_type=sender_type,
        recipient_type=recipient_type,
        message_type=message_type,
        title=title,
        body=body or {},
        priority=max(1, min(5, priority)),
        ttl_seconds=ttl_seconds,
        target_message_id=target_message_id,
        status="pending",
    )
    db.add(msg)
    await db.flush()
    await db.refresh(msg)

    # Publish to Redis for real-time delivery
    await _publish_to_redis(msg)

    logger.info(
        "Mesh message %s: %s -> %s [%s]",
        msg.id, sender_type, recipient_type or "*broadcast*", title[:60],
    )
    return msg


# ─── Receive / Query ───────────────────────────────────────────────────────


async def get_pending_messages(
    db: AsyncSession,
    tenant_id: int,
    recipient_type: str,
    limit: int = 50,
) -> list[AgentMessage]:
    """Get all undelivered messages for an agent type.

    Args:
        db: Database session.
        tenant_id: Tenant scope.
        recipient_type: Agent type to fetch messages for.
        limit: Max messages to return.

    Returns:
        List of pending AgentMessage objects.
    """
    result = await db.execute(
        select(AgentMessage)
        .where(
            AgentMessage.tenant_id == tenant_id,
            or_(
                AgentMessage.recipient_type == recipient_type,
                AgentMessage.recipient_type.is_(None),  # broadcasts
            ),
            AgentMessage.status == "pending",
        )
        .order_by(AgentMessage.priority.desc(), AgentMessage.created_at.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_messages_for_agent(
    db: AsyncSession,
    tenant_id: int,
    agent_type: str,
    status: str | None = None,
    limit: int = 50,
) -> list[AgentMessage]:
    """Get all messages sent to an agent type, optionally filtered by status.

    Args:
        db: Database session.
        tenant_id: Tenant scope.
        agent_type: Agent type to fetch messages for.
        status: Optional status filter ('pending', 'delivered', 'read', 'failed').
        limit: Max messages to return.
    """
    conditions = [
        AgentMessage.tenant_id == tenant_id,
        or_(
            AgentMessage.recipient_type == agent_type,
            AgentMessage.recipient_type.is_(None),
        ),
    ]
    if status:
        conditions.append(AgentMessage.status == status)

    result = await db.execute(
        select(AgentMessage)
        .where(and_(*conditions))
        .order_by(AgentMessage.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def mark_delivered(
    db: AsyncSession,
    message_id: int,
    tenant_id: int,
) -> AgentMessage | None:
    """Mark a message as delivered."""
    result = await db.execute(
        select(AgentMessage).where(
            AgentMessage.id == message_id,
            AgentMessage.tenant_id == tenant_id,
        )
    )
    msg = result.scalar_one_or_none()
    if msg and msg.status == "pending":
        msg.status = "delivered"
        msg.delivered_at = datetime.now(timezone.utc)
        await db.flush()
    return msg


async def mark_read(
    db: AsyncSession,
    message_id: int,
    tenant_id: int,
) -> AgentMessage | None:
    """Mark a message as read (consumed by recipient agent)."""
    result = await db.execute(
        select(AgentMessage).where(
            AgentMessage.id == message_id,
            AgentMessage.tenant_id == tenant_id,
        )
    )
    msg = result.scalar_one_or_none()
    if msg:
        msg.status = "read"
        msg.read_at = datetime.now(timezone.utc)
        await db.flush()
    return msg


# ─── Broadcast ──────────────────────────────────────────────────────────────


async def broadcast(
    db: AsyncSession,
    tenant_id: int,
    sender_type: str,
    message_type: str,
    title: str,
    *,
    body: dict | None = None,
    priority: int = 3,
) -> AgentMessage:
    """Broadcast a message to all agents (recipient_type = None)."""
    return await send_message(
        db=db,
        tenant_id=tenant_id,
        sender_type=sender_type,
        recipient_type=None,
        message_type=message_type,
        title=title,
        body=body,
        priority=priority,
    )


# ─── Capability-Based Routing ───────────────────────────────────────────────


async def send_to_capability(
    db: AsyncSession,
    tenant_id: int,
    sender_type: str,
    capability: str,
    title: str,
    *,
    body: dict | None = None,
    min_tier: str | None = None,
    priority: int = 3,
) -> AgentMessage | None:
    """Send a message to the best agent that has a specific capability.

    Args:
        db: Database session.
        tenant_id: Tenant scope.
        sender_type: Agent type sending the message.
        capability: The capability to route by (e.g. 'web_search').
        title: Short message title.
        body: JSON payload.
        min_tier: Minimum agent tier filter.
        priority: 1-5 priority.

    Returns:
        The created AgentMessage, or None if no matching agent found.
    """
    matches = find_agents_by_capability(capability, min_tier=min_tier)
    if not matches:
        logger.warning(
            "No agents found for capability '%s' (sender=%s)", capability, sender_type,
        )
        return None

    # Route to the best match: prefer CORE > STANDARD > RESTRICTED
    tier_rank = {"core": 0, "standard": 1, "restricted": 2, "sandboxed": 3}
    best = min(matches, key=lambda m: tier_rank.get(m.get("tier", "standard"), 1))
    recipient = best["agent_type"]

    return await send_message(
        db=db,
        tenant_id=tenant_id,
        sender_type=sender_type,
        recipient_type=recipient,
        message_type="delegation",
        title=title,
        body=body,
        priority=priority,
    )


# ─── Cleanup ────────────────────────────────────────────────────────────────


async def delete_expired_messages(db: AsyncSession) -> int:
    """Delete messages past their TTL. Returns count deleted.

    Should be called periodically (e.g. via a Celery Beat task).
    """
    cutoff = datetime.now(timezone.utc)
    result = await db.execute(
        select(AgentMessage).where(
            AgentMessage.created_at < cutoff.timestamp() - AgentMessage.ttl_seconds  # type: ignore[operator]
        )
    )
    expired = list(result.scalars().all())
    count = len(expired)
    for msg in expired:
        await db.delete(msg)
    if count:
        await db.flush()
        logger.info("Deleted %s expired mesh messages", count)
    return count
