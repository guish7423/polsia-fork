"""Test BasePolsiaAgent.call_llm() — mock and API mode."""
import json

from app.agents.base import BasePolsiaAgent, register_agent, agent_map


@register_agent
class ConcreteAgent(BasePolsiaAgent):
    agent_type = "test_agent"

    async def run(self, db, context=None):
        return {"summary": "test run"}


def test_call_llm_returns_mock_when_env_set(monkeypatch):
    monkeypatch.setenv("LLM_API_MOCK", "true")
    monkeypatch.setenv("LLM_MOCK_RESPONSE", json.dumps({"result": "hello from mock"}))

    agent = ConcreteAgent()
    result = agent.call_llm("test prompt")

    assert result == {"result": "hello from mock"}


def test_call_llm_json_parses_mock(monkeypatch):
    monkeypatch.setenv("LLM_API_MOCK", "true")
    monkeypatch.setenv("LLM_MOCK_RESPONSE", json.dumps({"key": "value", "number": 42}))

    agent = ConcreteAgent()
    result = agent.call_llm("test")
    assert result == {"key": "value", "number": 42}


def test_register_agent_adds_to_map():
    assert "test_agent" in agent_map
    assert agent_map["test_agent"] == ConcreteAgent


def test_base_agent_raises_not_implemented():
    """BasePolsiaAgent.run() should raise if not overridden."""
    agent = BasePolsiaAgent()
    import pytest
    with pytest.raises(NotImplementedError):
        import asyncio
        asyncio.run(agent.run(None))
