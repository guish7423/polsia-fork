"""Tests for Phase RAG — Agent RAG context injection in call_llm()."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.agents.base import BasePolsiaAgent


class RAGTestAgent(BasePolsiaAgent):
    agent_type = "rag_test_agent"

    async def run(self, db, context=None):  # type: ignore[override]
        return {"summary": "rag test"}


# ── RAG disabled ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rag_disabled_does_not_inject(mocker):
    """When rag_enabled=False, no RAG context is injected even with tenant_id."""
    agent = RAGTestAgent()
    mocker.patch.dict("os.environ", {"LLM_API_MOCK": "false"})
    mocker.patch("app.agents.base.settings.rag_enabled", False)

    # Mock fallback chain
    fake_profile = MagicMock()
    fake_profile.name = "test-profile"
    fake_profile.model = "test-model"
    fake_profile.base_url = "https://api.test/v1"
    fake_profile.api_key.return_value = "test-key"
    mocker.patch("app.agents.base.fallback_chain", return_value=[fake_profile])

    # Mock httpx response
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

    # Ensure semantic_search_memory is never called
    mock_search = mocker.patch(
        "app.services.memory_service.semantic_search_memory",
        new_callable=AsyncMock,
    )

    result = await agent.call_llm("test prompt", db_session=MagicMock(), tenant_id=1)

    mock_search.assert_not_called()
    assert result.get("result") == "ok"


# ── RAG enabled with results ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rag_enabled_injects_context(mocker):
    """When rag_enabled=True and tenant_id provided, RAG context is injected."""
    agent = RAGTestAgent()
    mocker.patch.dict("os.environ", {"LLM_API_MOCK": "false"})
    mocker.patch("app.agents.base.settings.rag_enabled", True)

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

    # Mock semantic_search_memory to return entries
    entry1 = MagicMock()
    entry1.title = "Knowledge 1"
    entry1.content = "This is relevant knowledge."
    entry1.category = "strategy"
    entry1.source = "manual"

    entry2 = MagicMock()
    entry2.title = "Knowledge 2"
    entry2.content = "More relevant context."
    entry2.category = "research"
    entry2.source = "web"

    mock_search = mocker.patch(
        "app.services.memory_service.semantic_search_memory",
        new_callable=AsyncMock,
        return_value=[entry1, entry2],
    )

    await agent.call_llm("test prompt", db_session=MagicMock(), tenant_id=42)

    # Verify semantic_search_memory was called with the right args
    mock_search.assert_called_once()
    _call_kwargs = mock_search.call_args
    assert _call_kwargs[1]["query"] == "test prompt"
    assert _call_kwargs[1]["tenant_id"] == 42

    # Verify the HTTP request has RAG context in the user message
    sent_kwargs = mock_post.call_args
    assert sent_kwargs is not None
    messages = sent_kwargs[1]["json"]["messages"]
    user_msg = messages[-1]
    assert user_msg["role"] == "user"
    assert "test prompt" in user_msg["content"]
    assert "This is relevant knowledge." in user_msg["content"]
    assert "More relevant context." in user_msg["content"]


# ── RAG empty results ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rag_empty_results_no_injection(mocker):
    """When RAG returns no results, prompt is unchanged."""
    agent = RAGTestAgent()
    mocker.patch.dict("os.environ", {"LLM_API_MOCK": "false"})
    mocker.patch("app.agents.base.settings.rag_enabled", True)

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

    mocker.patch(
        "app.services.memory_service.semantic_search_memory",
        new_callable=AsyncMock,
        return_value=[],
    )

    await agent.call_llm("test prompt", db_session=MagicMock(), tenant_id=1)

    sent_kwargs = mock_post.call_args
    assert sent_kwargs is not None
    messages = sent_kwargs[1]["json"]["messages"]
    user_msg = messages[-1]
    assert user_msg["content"] == "test prompt"  # unchanged


# ── RAG exception safety (fail-open) ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_rag_exception_safety(mocker):
    """RAG service exception does not block agent execution (fail-open)."""
    agent = RAGTestAgent()
    mocker.patch.dict("os.environ", {"LLM_API_MOCK": "false"})
    mocker.patch("app.agents.base.settings.rag_enabled", True)

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

    mocker.patch(
        "app.services.memory_service.semantic_search_memory",
        new_callable=AsyncMock,
        side_effect=Exception("ChromaDB connection error"),
    )

    result = await agent.call_llm("test prompt", db_session=MagicMock(), tenant_id=1)

    assert result.get("result") == "ok"


# ── Backward compatibility: tenant_id=None ────────────────────────────────────


@pytest.mark.asyncio
async def test_rag_tenant_id_none_backward_compatible(mocker):
    """When tenant_id=None, no RAG context is injected (backward compat)."""
    agent = RAGTestAgent()
    mocker.patch.dict("os.environ", {"LLM_API_MOCK": "false"})
    mocker.patch("app.agents.base.settings.rag_enabled", True)

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

    mock_search = mocker.patch(
        "app.services.memory_service.semantic_search_memory",
        new_callable=AsyncMock,
    )

    await agent.call_llm("test prompt", db_session=MagicMock())

    mock_search.assert_not_called()


# ── call_llm_stream RAG injection ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rag_stream_injects_context(mocker):
    """call_llm_stream injects RAG context when tenant_id is provided."""
    agent = RAGTestAgent()
    mocker.patch.dict("os.environ", {"LLM_API_MOCK": "false"})
    mocker.patch("app.agents.base.settings.rag_enabled", True)

    # Mock fallback chain to return a streaming instance
    from app.core.model_instance import StreamChunk

    fake_instance = MagicMock()
    fake_instance.name = "test-instance"

    async def _mock_chat_stream(*args, **kwargs):
        yield StreamChunk(content="chunk1")
        yield StreamChunk(content=" chunk2")
        yield StreamChunk(finish_reason="stop")

    fake_instance.chat_stream = _mock_chat_stream

    mocker.patch(
        "app.agents.base.fallback_instances",
        return_value=[fake_instance],
    )

    # Mock RAG search returning results
    entry = MagicMock()
    entry.title = "RAG Context"
    entry.content = "Streaming RAG context."
    entry.category = "research"
    entry.source = "manual"

    mock_search = mocker.patch(
        "app.services.memory_service.semantic_search_memory",
        new_callable=AsyncMock,
        return_value=[entry],
    )

    chunks: list[str] = []
    async for chunk in agent.call_llm_stream(
        "test stream prompt",
        tenant_id=42,
    ):
        if chunk.content:
            chunks.append(chunk.content)

    assert "".join(chunks) == "chunk1 chunk2"

    # Verify RAG context was added to the messages
    call_kwargs = fake_instance.chat_stream.call_args
    assert call_kwargs is not None
    messages = call_kwargs[1]["messages"]
    user_msg = messages[-1]
    assert user_msg["role"] == "user"
    assert "test stream prompt" in user_msg["content"]
    assert "Streaming RAG context." in user_msg["content"]

    mock_search.assert_called_once()
    assert mock_search.call_args[1]["tenant_id"] == 42
