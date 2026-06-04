"""Tests for ToolRunner — tool definition building and execution."""

import json

import pytest

from app.services.mcp_gateway import register_tool

SAMPLE_SCHEMA = {
    "type": "object",
    "properties": {
        "q": {"type": "string", "description": "Search query"},
    },
    "required": ["q"],
}


async def _register_tool(db, tenant_id=1, name="web_search",
                         endpoint="https://httpbin.org/post",
                         schema_json=None):
    return await register_tool(
        db, tenant_id=tenant_id, name=name, description="Test tool",
        endpoint=endpoint, schema_json=schema_json or {},
    )


class TestBuildToolsDefs:
    """ToolRunner._build_tools_defs() — MCPTool → OpenAI function defs."""

    @pytest.mark.asyncio
    async def test_build_tools_defs_from_mcp(self, async_db_session):
        """Load tools from DB and produce correct OpenAI format."""
        from app.services.tool_runner import ToolRunner

        await _register_tool(
            async_db_session, tenant_id=1, name="web_search",
            schema_json=SAMPLE_SCHEMA,
        )

        defs = await ToolRunner._build_tools_defs(tenant_id=1, db=async_db_session)

        assert len(defs) == 1
        entry = defs[0]
        assert entry["type"] == "function"
        assert entry["function"]["name"] == "web_search"
        assert entry["function"]["description"] == "Test tool"
        assert entry["function"]["parameters"] == SAMPLE_SCHEMA

    @pytest.mark.asyncio
    async def test_build_tools_defs_empty(self, async_db_session):
        """No tools registered → empty list."""
        from app.services.tool_runner import ToolRunner

        defs = await ToolRunner._build_tools_defs(tenant_id=1, db=async_db_session)
        assert defs == []

    @pytest.mark.asyncio
    async def test_build_tools_defs_skips_disabled(self, async_db_session):
        """Disabled tools are excluded from definitions."""
        from app.services.mcp_gateway import register_tool as reg
        from app.services.tool_runner import ToolRunner

        await reg(
            async_db_session, tenant_id=1, name="enabled_tool",
            description="", endpoint="https://e.com",
            schema_json={}, enabled=True,
        )
        await reg(
            async_db_session, tenant_id=1, name="disabled_tool",
            description="", endpoint="https://d.com",
            schema_json={}, enabled=False,
        )

        defs = await ToolRunner._build_tools_defs(tenant_id=1, db=async_db_session)
        names = [d["function"]["name"] for d in defs]
        assert "enabled_tool" in names
        assert "disabled_tool" not in names


class TestExecuteSingleTool:
    """ToolRunner._execute_single_tool() — name→ID resolution + execution + formatting."""

    @pytest.mark.asyncio
    async def test_execute_single_tool_call(self, async_db_session, mocker):
        """Resolve name→ID, execute tool, return tool-role message."""
        mocker.patch(
            "app.services.mcp_gateway.MCPClient.call_tool",
            return_value={"result": "mocked"},
        )

        await _register_tool(
            async_db_session, tenant_id=1, name="echo",
            schema_json=SAMPLE_SCHEMA,
        )

        from app.services.tool_runner import ToolRunner

        tool_call = {
            "id": "call_abc123",
            "type": "function",
            "function": {
                "name": "echo",
                "arguments": '{"q": "hello"}',
            },
        }

        result = await ToolRunner._execute_single_tool(
            tool_call, tenant_id=1, db=async_db_session,
        )

        assert result["role"] == "tool"
        assert result["tool_call_id"] == "call_abc123"
        content = json.loads(result["content"])
        assert content["result"] == "mocked"

    @pytest.mark.asyncio
    async def test_tool_name_not_found(self, async_db_session):
        """Unknown tool name returns error gracefully."""
        from app.services.tool_runner import ToolRunner

        tool_call = {
            "id": "call_unknown",
            "type": "function",
            "function": {
                "name": "nonexistent_tool",
                "arguments": "{}",
            },
        }

        result = await ToolRunner._execute_single_tool(
            tool_call, tenant_id=1, db=async_db_session,
        )

        assert result["role"] == "tool"
        assert result["tool_call_id"] == "call_unknown"
        content = json.loads(result["content"])
        assert "error" in content
        assert "Unknown tool" in content["error"]

    @pytest.mark.asyncio
    async def test_tool_execution_failure(self, async_db_session, mocker):
        """Tool execution error returns error-format message."""
        mocker.patch(
            "app.services.mcp_gateway.MCPClient.call_tool",
            side_effect=Exception("Connection refused"),
        )

        await _register_tool(
            async_db_session, tenant_id=1, name="faulty",
        )

        from app.services.tool_runner import ToolRunner

        tool_call = {
            "id": "call_faulty",
            "type": "function",
            "function": {
                "name": "faulty",
                "arguments": "{}",
            },
        }

        result = await ToolRunner._execute_single_tool(
            tool_call, tenant_id=1, db=async_db_session,
        )

        assert result["role"] == "tool"
        content = json.loads(result["content"])
        assert "error" in content

    @pytest.mark.asyncio
    async def test_invalid_arguments(self, async_db_session, mocker):
        """Invalid JSON arguments return error gracefully."""
        await _register_tool(
            async_db_session, tenant_id=1, name="picker",
        )

        from app.services.tool_runner import ToolRunner

        tool_call = {
            "id": "call_bad_args",
            "type": "function",
            "function": {
                "name": "picker",
                "arguments": "not-valid-json",
            },
        }

        result = await ToolRunner._execute_single_tool(
            tool_call, tenant_id=1, db=async_db_session,
        )

        assert result["role"] == "tool"
        content = json.loads(result["content"])
        assert "error" in content


class TestExecuteToolCalls:
    """ToolRunner._execute_tool_calls() — batch execution from one LLM response."""

    @pytest.mark.asyncio
    async def test_execute_multiple_tool_calls(self, async_db_session, mocker):
        """Execute parallel tool calls from one LLM response."""
        mocker.patch(
            "app.services.mcp_gateway.MCPClient.call_tool",
            return_value={"result": "ok"},
        )

        await _register_tool(async_db_session, tenant_id=1, name="tool_a")
        await _register_tool(async_db_session, tenant_id=1, name="tool_b")

        from app.services.tool_runner import ToolRunner

        tool_calls = [
            {"id": "call_1", "type": "function", "function": {"name": "tool_a", "arguments": "{}"}},
            {"id": "call_2", "type": "function", "function": {"name": "tool_b", "arguments": "{}"}},
        ]

        results = await ToolRunner._execute_tool_calls(
            tool_calls, tenant_id=1, db=async_db_session,
        )

        assert len(results) == 2
        assert results[0]["tool_call_id"] == "call_1"
        assert results[1]["tool_call_id"] == "call_2"
        assert all(r["role"] == "tool" for r in results)

    @pytest.mark.asyncio
    async def test_empty_tool_calls(self, async_db_session):
        """Empty tool_calls list returns empty results list."""
        from app.services.tool_runner import ToolRunner

        results = await ToolRunner._execute_tool_calls(
            [], tenant_id=1, db=async_db_session,
        )
        assert results == []
