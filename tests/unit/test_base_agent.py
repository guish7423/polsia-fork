"""Test BasePolsiaAgent.call_llm() — mock, API mode, and gen config merging."""
import json
import pytest

from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.base import BasePolsiaAgent, register_agent, agent_map


@register_agent
class ConcreteAgent(BasePolsiaAgent):
    agent_type = "test_agent"

    async def run(self, db, context=None):
        return {"summary": "test run"}


@pytest.mark.asyncio
async def test_call_llm_returns_mock_when_env_set(monkeypatch):
    monkeypatch.setenv("LLM_API_MOCK", "true")

    agent = ConcreteAgent()
    result = await agent.call_llm("test prompt")

    assert isinstance(result, dict)
    assert "result" in result


@pytest.mark.asyncio
async def test_call_llm_json_parses_mock(monkeypatch):
    monkeypatch.setenv("LLM_API_MOCK", "true")

    agent = ConcreteAgent()
    result = await agent.call_llm("test")
    assert isinstance(result, dict)
    assert "result" in result


def test_register_agent_adds_to_map():
    assert "test_agent" in agent_map
    assert agent_map["test_agent"] == ConcreteAgent


def test_base_agent_raises_not_implemented():
    """BasePolsiaAgent.run() should raise if not overridden."""
    agent = BasePolsiaAgent()
    with pytest.raises(NotImplementedError):
        import asyncio
        asyncio.run(agent.run(None))


# ── Gen Config override tests ────────────────────────────────────────────────

@pytest.fixture
def agent():
    return ConcreteAgent()


@pytest.mark.asyncio
async def test_gen_config_merged_into_call_llm_kwargs(agent, mocker):
    """ConfigTunerService overrides are merged into LLM request kwargs."""
    # Disable mock mode so we reach the real httpx path
    mocker.patch.dict("os.environ", {"LLM_API_MOCK": "false"})
    mocker.patch("app.agents.base.settings.config_tuner_enabled", True)

    # Mock fallback_chain to return a single profile
    fake_profile = MagicMock()
    fake_profile.name = "test-profile"
    fake_profile.model = "test-model"
    fake_profile.base_url = "https://api.test/v1"
    fake_profile.api_key.return_value = "test-key"

    mocker.patch("app.agents.base.fallback_chain", return_value=[fake_profile])

    # Mock httpx client to record what was sent
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json = MagicMock(return_value={
        "choices": [{"message": {"content": '{"result": "ok"}'}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10},
    })

    mock_post = AsyncMock(return_value=fake_resp)
    mock_client_cls = mocker.patch("httpx.AsyncClient")
    mock_client = mock_client_cls.return_value.__aenter__.return_value
    mock_client.post = mock_post

    # Mock ConfigTunerService.get_effective_config
    mock_get_config = mocker.patch(
        "app.services.config_tuner.ConfigTunerService.get_effective_config",
        new_callable=AsyncMock,
        return_value={
            "temperature": 0.3,
            "max_tokens": 4096,
            "top_p": 0.9,
        },
    )

    await agent.call_llm("test prompt", db_session=MagicMock())

    # Verify ConfigTunerService was consulted
    mock_get_config.assert_called_once()

    # Verify the merged overrides were sent in the request body
    call_kwargs = mock_post.call_args
    assert call_kwargs is not None
    body = call_kwargs[1]["json"]
    assert body["temperature"] == 0.3, f"Expected 0.3, got {body.get('temperature')}"
    assert body["max_tokens"] == 4096
    assert body["top_p"] == 0.9


@pytest.mark.asyncio
async def test_gen_config_skipped_when_disabled(agent, mocker):
    """No config lookup when config_tuner_enabled is False."""
    mocker.patch.dict("os.environ", {"LLM_API_MOCK": "false"})
    mocker.patch("app.agents.base.settings.config_tuner_enabled", False)

    fake_profile = MagicMock()
    fake_profile.name = "test-profile"
    fake_profile.model = "test-model"
    fake_profile.base_url = "https://api.test/v1"
    fake_profile.api_key.return_value = "test-key"

    mocker.patch("app.agents.base.fallback_chain", return_value=[fake_profile])

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json = MagicMock(return_value={
        "choices": [{"message": {"content": '{"result": "ok"}'}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10},
    })

    mock_post = AsyncMock(return_value=fake_resp)
    mock_client_cls = mocker.patch("httpx.AsyncClient")
    mock_client = mock_client_cls.return_value.__aenter__.return_value
    mock_client.post = mock_post

    mock_get_config = mocker.patch(
        "app.services.config_tuner.ConfigTunerService.get_effective_config",
        new_callable=AsyncMock,
    )

    await agent.call_llm("test prompt", db_session=MagicMock())

    # ConfigTunerService should NOT be called when disabled
    mock_get_config.assert_not_called()

    # Default temperature should remain (0.7 from build_request_kwargs)
    call_kwargs = mock_post.call_args
    assert call_kwargs is not None
    body = call_kwargs[1]["json"]
    assert body["temperature"] == 0.7


@pytest.mark.asyncio
async def test_gen_config_fail_open_on_service_error(agent, mocker):
    """Service error does not block agent execution (fail-open)."""
    mocker.patch.dict("os.environ", {"LLM_API_MOCK": "false"})
    mocker.patch("app.agents.base.settings.config_tuner_enabled", True)

    fake_profile = MagicMock()
    fake_profile.name = "test-profile"
    fake_profile.model = "test-model"
    fake_profile.base_url = "https://api.test/v1"
    fake_profile.api_key.return_value = "test-key"

    mocker.patch("app.agents.base.fallback_chain", return_value=[fake_profile])

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json = MagicMock(return_value={
        "choices": [{"message": {"content": '{"result": "ok"}'}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10},
    })

    mock_post = AsyncMock(return_value=fake_resp)
    mock_client_cls = mocker.patch("httpx.AsyncClient")
    mock_client = mock_client_cls.return_value.__aenter__.return_value
    mock_client.post = mock_post

    # Simulate ConfigTunerService throwing an error
    mock_get_config = mocker.patch(
        "app.services.config_tuner.ConfigTunerService.get_effective_config",
        new_callable=AsyncMock,
        side_effect=Exception("DB connection error"),
    )

    result = await agent.call_llm("test prompt", db_session=MagicMock())

    # Should succeed despite error (fail-open)
    assert result.get("result") == "ok"
    mock_get_config.assert_called_once()


@pytest.mark.asyncio
async def test_gen_config_empty_config_uses_defaults(agent, mocker):
    """Empty config from ConfigTunerService uses existing defaults."""
    mocker.patch.dict("os.environ", {"LLM_API_MOCK": "false"})
    mocker.patch("app.agents.base.settings.config_tuner_enabled", True)

    fake_profile = MagicMock()
    fake_profile.name = "test-profile"
    fake_profile.model = "test-model"
    fake_profile.base_url = "https://api.test/v1"
    fake_profile.api_key.return_value = "test-key"

    mocker.patch("app.agents.base.fallback_chain", return_value=[fake_profile])

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json = MagicMock(return_value={
        "choices": [{"message": {"content": '{"result": "ok"}'}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10},
    })

    mock_post = AsyncMock(return_value=fake_resp)
    mock_client_cls = mocker.patch("httpx.AsyncClient")
    mock_client = mock_client_cls.return_value.__aenter__.return_value
    mock_client.post = mock_post

    # Return empty config (no overrides)
    mocker.patch(
        "app.services.config_tuner.ConfigTunerService.get_effective_config",
        new_callable=AsyncMock,
        return_value={},
    )

    await agent.call_llm("test prompt", db_session=MagicMock())

    # Default temperature (0.7) should be preserved
    call_kwargs = mock_post.call_args
    assert call_kwargs is not None
    body = call_kwargs[1]["json"]
    assert body["temperature"] == 0.7
    assert "max_tokens" not in body
    assert "top_p" not in body
