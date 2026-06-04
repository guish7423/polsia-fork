"""Test BasePolsiaAgent mesh communication methods."""

import pytest

from app.agents.base import BasePolsiaAgent


@pytest.fixture
def agent():
    a = BasePolsiaAgent()
    a.agent_type = "test_agent"
    return a


class TestAgentSendMessage:
    @pytest.mark.asyncio
    async def test_send_message(self, agent, async_db_session, mock_redis):
        result = await agent.send_message(
            async_db_session,
            message_type="generic",
            title="Hello from test",
            recipient_type="orchestrator",
            body={"key": "value"},
        )
        assert result["status"] == "sent"
        assert "message_id" in result

    @pytest.mark.asyncio
    async def test_send_broadcast(self, agent, async_db_session, mock_redis):
        result = await agent.send_message(
            async_db_session,
            message_type="broadcast",
            title="All agents attention",
        )
        assert result["status"] == "sent"


class TestAgentReceiveMessages:
    @pytest.mark.asyncio
    async def test_receive_pending_messages(self, agent, async_db_session, mock_redis):
        # Send a message to test_agent first
        from app.services.mesh_bus import send_message

        await send_message(
            async_db_session, 1, "orchestrator",
            "delegation", "Do something",
            recipient_type="test_agent",
        )
        messages = await agent.receive_messages(async_db_session)
        assert len(messages) >= 1
        assert messages[0]["sender_type"] == "orchestrator"


class TestAgentCapabilityQuery:
    def test_query_capabilities(self, agent):
        results = agent.query_capabilities("web_search")
        assert len(results) >= 1
        assert results[0]["agent_type"] == "market_intel"

    def test_query_capabilities_unknown(self, agent):
        results = agent.query_capabilities("unknown_capability")
        assert results == []


class TestAgentDelegate:
    @pytest.mark.asyncio
    async def test_delegate_to_agent(self, agent, async_db_session, mock_redis):
        result = await agent.delegate_to_agent(
            async_db_session,
            capability="web_search",
            title="Search for competitors",
            body={"query": "AI startups 2026"},
        )
        assert result["status"] == "delegated"
        assert result["target_agent"] == "market_intel"

    @pytest.mark.asyncio
    async def test_delegate_no_match(self, agent, async_db_session, mock_redis):
        result = await agent.delegate_to_agent(
            async_db_session,
            capability="nonexistent_ability",
            title="Impossible task",
        )
        assert result["status"] == "no_agent_found"
