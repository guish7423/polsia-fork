"""Test AgentMessage model CRUD and defaults."""

import pytest
from sqlalchemy import select

from app.models.agent_message import AgentMessage


@pytest.mark.asyncio
async def test_create_agent_message(async_db_session):
    msg = AgentMessage(
        tenant_id=1,
        sender_type="competitor_research",
        recipient_type="social_media",
        message_type="delegation",
        title="New competitor alert",
        body={"competitor": "Acme Corp", "threat_level": "high"},
    )
    async_db_session.add(msg)
    await async_db_session.flush()
    await async_db_session.refresh(msg)

    assert msg.id is not None
    assert msg.status == "pending"
    assert msg.sender_type == "competitor_research"
    assert msg.recipient_type == "social_media"
    assert msg.message_type == "delegation"


@pytest.mark.asyncio
async def test_agent_message_default_ttl(async_db_session):
    msg = AgentMessage(
        tenant_id=1,
        sender_type="orchestrator",
        recipient_type="finance",
        message_type="generic",
        title="Monthly report request",
    )
    async_db_session.add(msg)
    await async_db_session.flush()

    assert msg.ttl_seconds == 86400  # 24h default


@pytest.mark.asyncio
async def test_agent_message_priority_default(async_db_session):
    msg = AgentMessage(
        tenant_id=1,
        sender_type="monitor",
        message_type="broadcast",
        title="System health alert",
    )
    async_db_session.add(msg)
    await async_db_session.flush()

    assert msg.priority == 3


@pytest.mark.asyncio
async def test_agent_message_broadcast_no_recipient(async_db_session):
    """Broadcast messages have recipient_type=None."""
    msg = AgentMessage(
        tenant_id=1,
        sender_type="monitor",
        message_type="broadcast",
        title="All clear",
    )
    async_db_session.add(msg)
    await async_db_session.flush()

    assert msg.recipient_type is None
    assert msg.message_type == "broadcast"


@pytest.mark.asyncio
async def test_agent_message_query_by_sender(async_db_session):
    for i in range(3):
        async_db_session.add(AgentMessage(
            tenant_id=1,
            sender_type="social_media",
            recipient_type="orchestrator",
            message_type="generic",
            title=f"Post report {i}",
        ))
    await async_db_session.flush()

    result = await async_db_session.execute(
        select(AgentMessage).where(AgentMessage.sender_type == "social_media")
    )
    msgs = result.scalars().all()
    assert len(msgs) == 3
