"""Mesh-aware Celery tasks — message processing and expiration cleanup."""

from __future__ import annotations

import json
import logging

from app.core.database import async_session
from app.models.agent_message import AgentMessage
from app.services import mesh_bus
from celery_app.worker import app as celery

logger = logging.getLogger(__name__)


# ── Async core (testable directly, no asyncio.run() in tests) ──────────────

async def process_mesh_message_async(
    message_id: int,
    tenant_id: int = 1,
) -> dict:
    """Async core of process_mesh_message — testable with @pytest.mark.asyncio.

    Args:
        message_id: The AgentMessage ID.
        tenant_id: Tenant scope.

    Returns:
        Dict with processing result.
    """
    async with async_session() as db:
        from sqlalchemy import select
        result = await db.execute(
            select(AgentMessage).where(
                AgentMessage.id == message_id,
                AgentMessage.tenant_id == tenant_id,
            )
        )
        msg = result.scalar_one_or_none()
        if not msg:
            logger.warning("Mesh message %s not found", message_id)
            return {"status": "not_found", "message_id": message_id}

        # Skip broadcasts — agents poll for broadcasts
        if msg.recipient_type is None:
            return {"status": "broadcast_skipped", "message_id": message_id}

        # Mark delivered
        await mesh_bus.mark_delivered(db, message_id, tenant_id)

        # Trigger the target agent to process this message
        from celery_app.tasks.agent_tasks import run_agent

        run_agent.delay(
            agent_type=msg.recipient_type,
            context={
                "mesh_message_id": message_id,
                "sender": msg.sender_type,
                "title": msg.title,
                "description": f"Mesh message from {msg.sender_type}: {msg.title}",
                "source": "mesh",
                "mesh_body": msg.body,
            },
        )

        logger.info(
            "Dispatched mesh message %s to agent %s",
            message_id, msg.recipient_type,
        )
        return {
            "status": "dispatched",
            "message_id": message_id,
            "target_agent": msg.recipient_type,
        }


async def cleanup_expired_mesh_messages_async() -> dict:
    """Async core of cleanup_expired_mesh_messages — testable directly."""
    async with async_session() as db:
        count = await mesh_bus.delete_expired_messages(db)
        await db.commit()
        return {"deleted": count}


# ── Celery sync wrappers (thin: asyncio.run() is the only event loop) ─────

@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def process_mesh_message(self, message_id: int, tenant_id: int = 1) -> dict:
    """Celery task wrapper — calls the async core via asyncio.run()."""
    import asyncio
    return asyncio.run(process_mesh_message_async(message_id, tenant_id))


@celery.task
def cleanup_expired_mesh_messages() -> dict:
    """Celery task wrapper — calls the async core via asyncio.run()."""
    import asyncio
    return asyncio.run(cleanup_expired_mesh_messages_async())
