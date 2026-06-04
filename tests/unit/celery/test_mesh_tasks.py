"""Test mesh-aware Celery tasks.

IMPORTANT: Tests call the async core functions directly (not the Celery sync
wrappers) to avoid RuntimeError from asyncio.run() inside an async test.
"""

import pytest
from unittest.mock import patch, AsyncMock

from app.services.mesh_bus import send_message, broadcast


class TestProcessMeshMessage:
    """Tests for process_mesh_message_async() — async core, testable directly."""

    @pytest.mark.asyncio
    async def test_dispatches_to_target_agent(self, async_db_session, mock_redis):
        """Verify message dispatches run_agent.delay to the correct agent."""
        msg = await send_message(
            async_db_session, 1, "competitor_research",
            "delegation", "New data",
            recipient_type="social_media",
        )
        with (
            patch("celery_app.tasks.agent_tasks.run_agent.delay") as mock_delay,
            patch("celery_app.tasks.mesh_tasks.async_session") as mock_session,
        ):
            mock_session.return_value.__aenter__.return_value = async_db_session
            from celery_app.tasks.mesh_tasks import process_mesh_message_async
            result = await process_mesh_message_async(msg.id, tenant_id=1)

            assert result["status"] == "dispatched"
            mock_delay.assert_called_once()
            # Verify the target agent matches the message recipient
            call_kwargs = mock_delay.call_args[1]
            assert call_kwargs["agent_type"] == "social_media"

    @pytest.mark.asyncio
    async def test_not_found(self, async_db_session, mock_redis):
        """Non-existent message returns not_found status."""
        with patch("celery_app.tasks.mesh_tasks.async_session") as mock_session:
            mock_session.return_value.__aenter__.return_value = async_db_session
            from celery_app.tasks.mesh_tasks import process_mesh_message_async
            result = await process_mesh_message_async(99999, tenant_id=1)
            assert result["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_broadcast_skipped(self, async_db_session, mock_redis):
        """Broadcast messages are NOT dispatched (agents poll instead)."""
        msg = await broadcast(
            async_db_session, 1, "monitor", "broadcast", "Health check",
        )
        with (
            patch("celery_app.tasks.agent_tasks.run_agent.delay") as mock_delay,
            patch("celery_app.tasks.mesh_tasks.async_session") as mock_session,
        ):
            mock_session.return_value.__aenter__.return_value = async_db_session
            from celery_app.tasks.mesh_tasks import process_mesh_message_async
            result = await process_mesh_message_async(msg.id, tenant_id=1)

            assert result["status"] == "broadcast_skipped"
            mock_delay.assert_not_called()


class TestCleanupExpired:
    @pytest.mark.asyncio
    async def test_cleanup_expired_messages(self, async_db_session, mock_redis):
        """Verify expired message deletion returns a count."""
        with patch("celery_app.tasks.mesh_tasks.async_session") as mock_session:
            mock_session.return_value.__aenter__.return_value = async_db_session
            from celery_app.tasks.mesh_tasks import cleanup_expired_mesh_messages_async
            result = await cleanup_expired_mesh_messages_async()
            assert "deleted" in result
