"""Tests for call_llm_with_tools — multi-round LLM+tool execution.

Uses direct mocking of model_instance.chat() and ToolRunner to
test the round-loop logic, tool-call execution, and JSON parsing
without needing real API calls.
"""

import json

import pytest
from unittest.mock import AsyncMock

from app.core.model_instance import ChatResult, ModelInstance
from app.services.model_router import select_instance


# ── Helpers ────────────────────────────────────────────────────────────────────


def _chat_result(
    content: str | None = None,
    tool_calls: list[dict] | None = None,
) -> ChatResult:
    """Build a ChatResult with realistic ``raw`` structure.

    Args:
        content: Assistant message text (``None`` when tools-only).
        tool_calls: OpenAI-format tool call list.
    """
    msg: dict = {"role": "assistant"}
    if content is not None:
        msg["content"] = content
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return ChatResult(
        content=content or "",
        raw={"choices": [{"message": msg, "finish_reason": "stop"}]},
        success=True,
        model="mock",
        provider="mock",
    )


_SAMPLE_TOOL_DEFS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web",
            "parameters": {
                "type": "object",
                "properties": {"q": {"type": "string"}},
                "required": ["q"],
            },
        },
    },
]

_SAMPLE_TOOL_CALLS = [
    {
        "id": "call_abc",
        "type": "function",
        "function": {"name": "web_search", "arguments": '{"q": "test"}'},
    },
]

_TOOL_RESULT = {
    "role": "tool",
    "tool_call_id": "call_abc",
    "content": json.dumps({"result": "mocked tool output"}),
}


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _mock_tool_runner(mocker):
    """Patch ToolRunner to return known data without DB access."""
    mocker.patch(
        "app.services.tool_runner.ToolRunner._build_tools_defs",
        return_value=_SAMPLE_TOOL_DEFS,
    )
    mocker.patch(
        "app.services.tool_runner.ToolRunner._execute_single_tool",
        return_value=_TOOL_RESULT,
    )


@pytest.fixture
def mock_chat(mocker):
    """Return a factory that creates a mocked ``model_instance.chat()``.

    Usage::

        mock_chat.side_effect = [_chat_result("first"), _chat_result("second")]

    Each call to ``model_instance.chat()`` returns the next element.
    """
    inst = AsyncMock(spec=ModelInstance)
    inst.model = "mock"
    inst.name = "Mock (test)"
    # Default: return empty content
    inst.chat = AsyncMock(return_value=_chat_result(""))
    mocker.patch("app.agents.tool_agent.select_instance", return_value=inst)
    return inst.chat


# ── The agent subclass used by tests ──────────────────────────────────────────


class _TestAgent:
    """Minimal agent-like object for testing call_llm_with_tools.

    Mirrors the interface that ``BasePolsiaAgent.call_llm_with_tools()``
    presents — just enough to exercise the standalone function.
    """

    agent_type = "test_agent"
    task_category = None

    async def call_llm_with_tools(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tool_rounds: int = 5,
        task_category=None,
        db_session=None,
        tenant_id: int | None = None,
    ) -> dict:
        from app.agents.tool_agent import call_llm_with_tools as _call

        return await _call(
            agent_type=self.agent_type,
            task_category=self.task_category,
            prompt=prompt,
            system_prompt=system_prompt,
            max_tool_rounds=max_tool_rounds,
            task_category_override=task_category,
            db_session=db_session,
            tenant_id=tenant_id,
        )


# ── Tests ──────────────────────────────────────────────────────────────────────


class TestCallLlmWithToolsNoToolCalls:
    """LLM returns plain content without tool_calls."""

    @pytest.mark.asyncio
    async def test_no_tool_calls_returns_content(self, mock_chat):
        """Single round, no tool_calls — content returned in result dict."""
        mock_chat.return_value = _chat_result("Hello, world!")
        agent = _TestAgent()
        result = await agent.call_llm_with_tools(prompt="Hi")
        assert result["result"] == "Hello, world!"

    @pytest.mark.asyncio
    async def test_no_tool_calls_final_json_round(self, mock_chat):
        """Final round without tools parses JSON from content."""
        mock_chat.return_value = _chat_result(json.dumps({"key": "value"}))
        agent = _TestAgent()
        result = await agent.call_llm_with_tools(
            prompt="Give JSON", max_tool_rounds=1,
        )
        # max_tool_rounds=1 means the only round IS the final round,
        # so it should attempt JSON parsing and return as dict
        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_no_tool_calls_invalid_json(self, mock_chat):
        """Invalid JSON on final round falls back to result wrapper."""
        mock_chat.return_value = _chat_result("not-json")
        agent = _TestAgent()
        result = await agent.call_llm_with_tools(
            prompt="Give JSON", max_tool_rounds=1,
        )
        assert result["result"] == "not-json"


class TestCallLlmWithToolsOneRound:
    """One tool called, result fed back, final response returned."""

    @pytest.mark.asyncio
    async def test_single_tool_round(self, mock_chat, async_db_session):
        """Round 1: tool_calls → execute → feed back → Round 2: no calls."""
        mock_chat.side_effect = [
            _chat_result(content=None, tool_calls=_SAMPLE_TOOL_CALLS),  # Round 1
            _chat_result("Final answer after tool"),                    # Round 2
        ]
        agent = _TestAgent()
        result = await agent.call_llm_with_tools(
            prompt="Use tools", tenant_id=1, db_session=async_db_session,
        )
        assert result["result"] == "Final answer after tool"

    @pytest.mark.asyncio
    async def test_tool_result_appended_to_messages(self, mock_chat, mocker, async_db_session):
        """Tool result is appended to the message list for the next round."""
        mock_chat.side_effect = [
            _chat_result(content=None, tool_calls=_SAMPLE_TOOL_CALLS),
            _chat_result("Done"),
        ]
        agent = _TestAgent()
        await agent.call_llm_with_tools(
            prompt="Use tools", tenant_id=1, db_session=async_db_session,
        )

        # Second chat call should include the tool result in messages
        _call_args = mock_chat.call_args_list
        assert len(_call_args) == 2

        # Second call's messages should have assistant + tool messages appended
        second_messages = _call_args[1][1]["messages"]
        assert any(
            m.get("role") == "tool" for m in second_messages
        ), "Tool result should be in message history"


class TestCallLlmWithToolsMaxRounds:
    """Hits round limit, returns aggregated."""

    @pytest.mark.asyncio
    async def test_max_rounds_exceeded(self, mock_chat, async_db_session):
        """All rounds produce tool_calls → returns last content + _tool_rounds."""
        mock_chat.side_effect = [
            _chat_result(content=None, tool_calls=_SAMPLE_TOOL_CALLS),
            _chat_result(content=None, tool_calls=_SAMPLE_TOOL_CALLS),
            _chat_result(content=None, tool_calls=_SAMPLE_TOOL_CALLS),
        ]
        agent = _TestAgent()
        result = await agent.call_llm_with_tools(
            prompt="Loop", max_tool_rounds=3,
            tenant_id=1, db_session=async_db_session,
        )
        # Since every round produces tool_calls (including the 3rd/final),
        # we'll max out and return the aggregated result
        assert "_tool_rounds" in result
        assert result["_tool_rounds"] == 3


class TestCallLlmWithToolsNoToolsRegistered:
    """No tools available — acts like regular call_llm."""

    @pytest.mark.asyncio
    async def test_empty_tools_list(self, mock_chat, mocker):
        """Empty tools defs → no tools param passed, content returned."""
        mocker.patch(
            "app.services.tool_runner.ToolRunner._build_tools_defs",
            return_value=[],
        )
        mock_chat.return_value = _chat_result("No tools needed")
        agent = _TestAgent()
        result = await agent.call_llm_with_tools(
            prompt="Hello", tenant_id=1,
        )
        assert result["result"] == "No tools needed"

    @pytest.mark.asyncio
    async def test_tools_param_not_passed_when_empty(self, mock_chat, mocker):
        """Empty tools → ``tools`` kwarg not passed to chat()."""
        mocker.patch(
            "app.services.tool_runner.ToolRunner._build_tools_defs",
            return_value=[],
        )
        mock_chat.return_value = _chat_result("ok")
        agent = _TestAgent()
        await agent.call_llm_with_tools(prompt="Hi", tenant_id=1)

        # Verify tools was not in the kwargs
        _called_kwargs = mock_chat.call_args[1]
        assert "tools" not in _called_kwargs


class TestCallLlmWithToolsParamOnFinalRound:
    """tools param should NOT be passed in the final (JSON) round."""

    @pytest.mark.asyncio
    async def test_tools_omitted_on_final_round(self, mock_chat, async_db_session):
        """Final round (is_json_round=True) omits tools param."""
        mock_chat.side_effect = [
            _chat_result(content=None, tool_calls=_SAMPLE_TOOL_CALLS),
            _chat_result('{"final": true}'),
        ]
        agent = _TestAgent()
        await agent.call_llm_with_tools(
            prompt="Test", max_tool_rounds=2,
            tenant_id=1, db_session=async_db_session,
        )

        _call_args = mock_chat.call_args_list
        assert len(_call_args) == 2

        # First call: tools param present
        first_kwargs = _call_args[0][1]
        assert "tools" in first_kwargs, "Tools param should be in non-final round"
        assert first_kwargs["tools"] == _SAMPLE_TOOL_DEFS

        # Second call (final): tools param NOT present
        second_kwargs = _call_args[1][1]
        assert "tools" not in second_kwargs, "Tools param should be omitted on final round"


class TestCallLlmWithToolsNoInstance:
    """No model instance available — graceful fallback."""

    @pytest.mark.asyncio
    async def test_no_instance_returns_fallback(self, mocker):
        """select_instance returns None → fallback error dict."""
        mocker.patch("app.agents.tool_agent.select_instance", return_value=None)
        agent = _TestAgent()
        result = await agent.call_llm_with_tools(prompt="Hi")
        assert "error" in result
        assert "No LLM instance" in result["error"]


class TestCallLlmWithToolsApiFailure:
    """API/HTTP errors are surfaced gracefully."""

    @pytest.mark.asyncio
    async def test_chat_raises_exception(self, mock_chat):
        """chat() raises → returns error dict."""
        mock_chat.side_effect = RuntimeError("API timeout")
        agent = _TestAgent()
        result = await agent.call_llm_with_tools(prompt="Hi")
        assert "error" in result
