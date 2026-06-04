"""Test mesh bus — send, receive, broadcast, capability routing."""

import pytest
from unittest.mock import patch, AsyncMock

from app.services.mesh_bus import (
    send_message,
    get_pending_messages,
    broadcast,
    send_to_capability,
    mark_delivered,
    mark_read,
    get_messages_for_agent,
)


@pytest.fixture(autouse=True)
def _mock_redis_publish(mock_redis):
    """Prevent actual Redis calls in tests."""
    with patch("app.services.mesh_bus._publish_to_redis", AsyncMock()):
        yield


class TestSendMessages:
    @pytest.mark.asyncio
    async def test_send_direct_message(self, async_db_session):
        msg = await send_message(
            db=async_db_session,
            tenant_id=1,
            sender_type="competitor_research",
            recipient_type="social_media",
            message_type="delegation",
            title="New competitor data",
            body={"competitor": "Acme", "action": "create_post"},
        )
        assert msg.id is not None
        assert msg.status == "pending"
        assert msg.recipient_type == "social_media"

    @pytest.mark.asyncio
    async def test_priority_clamping(self, async_db_session):
        msg = await send_message(
            db=async_db_session, tenant_id=1,
            sender_type="monitor", recipient_type="orchestrator",
            message_type="generic", title="test", priority=10,
        )
        assert msg.priority == 5  # clamped

    @pytest.mark.asyncio
    async def test_send_broadcast(self, async_db_session):
        msg = await broadcast(
            db=async_db_session, tenant_id=1,
            sender_type="monitor",
            message_type="broadcast",
            title="System health: all good",
        )
        assert msg.recipient_type is None
        assert msg.message_type == "broadcast"


class TestReceiveMessages:
    @pytest.mark.asyncio
    async def test_get_pending_messages(self, async_db_session):
        # Send 2 messages to social_media
        await send_message(
            async_db_session, 1, "competitor_research", "delegation", "Data 1",
            recipient_type="social_media",
        )
        await send_message(
            async_db_session, 1, "orchestrator", "delegation", "Data 2",
            recipient_type="social_media",
        )
        pending = await get_pending_messages(
            async_db_session, tenant_id=1, recipient_type="social_media",
        )
        assert len(pending) == 2

    @pytest.mark.asyncio
    async def test_get_messages_includes_broadcasts(self, async_db_session):
        """Pending messages query includes broadcast messages."""
        await broadcast(
            async_db_session, 1, "monitor", "broadcast", "System update",
        )
        pending = await get_pending_messages(
            async_db_session, tenant_id=1, recipient_type="social_media",
        )
        assert len(pending) == 1  # broadcast matched


class TestMessageStatusLifecycle:
    @pytest.mark.asyncio
    async def test_mark_delivered(self, async_db_session):
        msg = await send_message(
            async_db_session, 1, "a", "generic", "test",
            recipient_type="b",
        )
        updated = await mark_delivered(async_db_session, msg.id, 1)
        assert updated is not None
        assert updated.status == "delivered"
        assert updated.delivered_at is not None

    @pytest.mark.asyncio
    async def test_mark_read_from_delivered(self, async_db_session):
        msg = await send_message(
            async_db_session, 1, "a", "generic", "test",
            recipient_type="b",
        )
        await mark_delivered(async_db_session, msg.id, 1)
        updated = await mark_read(async_db_session, msg.id, 1)
        assert updated.status == "read"
        assert updated.read_at is not None


class TestCapabilityRouting:
    @pytest.mark.asyncio
    async def test_send_to_capability(self, async_db_session):
        msg = await send_to_capability(
            async_db_session, 1, "orchestrator",
            capability="web_search",
            title="Search for competitors",
            body={"query": "AI startup funding 2026"},
        )
        assert msg is not None
        assert msg.recipient_type == "market_intel"
        assert msg.message_type == "delegation"

    @pytest.mark.asyncio
    async def test_send_to_unknown_capability(self, async_db_session):
        msg = await send_to_capability(
            async_db_session, 1, "orchestrator",
            capability="quantum_computing",
            title="Q task",
        )
        assert msg is None  # No matching agent


class TestGetMessagesForAgent:
    @pytest.mark.asyncio
    async def test_filter_by_status(self, async_db_session):
        msg1 = await send_message(
            async_db_session, 1, "a", "generic", "urgent",
            recipient_type="social_media", priority=5,
        )
        await send_message(
            async_db_session, 1, "b", "generic", "normal",
            recipient_type="social_media",
        )
        await mark_delivered(async_db_session, msg1.id, 1)

        pending = await get_messages_for_agent(
            async_db_session, 1, "social_media", status="pending",
        )
        delivered = await get_messages_for_agent(
            async_db_session, 1, "social_media", status="delivered",
        )
        assert len(pending) == 1
        assert len(delivered) == 1
