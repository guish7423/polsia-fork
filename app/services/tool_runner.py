"""ToolRunner — builds OpenAI-compatible tool definitions and executes tool calls.

Used by `call_llm_with_tools()` to provide function-calling capabilities
to Polsia agents. Tools are loaded from the MCP Gateway registry and
converted to the OpenAI function definition format expected by
DeepSeek/OpenAI-compatible LLM APIs.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.mcp_gateway import execute_tool, get_tool_by_name, list_tools

logger = logging.getLogger(__name__)


class ToolRunner:
    """Service for managing tool definitions and executing tool calls.

    All methods are static so they can be called directly from
    agent execution paths without instantiating a service object.
    """

    # ── Tool Definition Building ─────────────────────────────────────────

    @staticmethod
    async def _build_tools_defs(
        tenant_id: int,
        db: AsyncSession,
        allowed_names: list[str] | None = None,
    ) -> list[dict]:
        """Load (and optionally filter) active MCPTool entries for *tenant_id*
        and convert to OpenAI-compatible function-definition format.

        Args:
            tenant_id: Tenant to scope tool lookup.
            db: Active database session.
            allowed_names: Optional allowlist of tool names. When set, only
                tools whose ``name`` appears in this list are included.
                ``None`` or empty = all enabled tools are included.

        Returns:
            A list of function-definition dicts for the ``tools`` parameter
            of DeepSeek/OpenAI chat-completion requests.
        """
        tools = await list_tools(db, tenant_id)
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.schema_json,
                },
            }
            for tool in tools
            if tool.enabled and (allowed_names is None or tool.name in allowed_names)
        ]

    # ── Single Tool Execution ────────────────────────────────────────────

    @staticmethod
    async def _execute_single_tool(
        tool_call: dict,
        tenant_id: int,
        db: AsyncSession,
    ) -> dict:
        """Resolve *tool_call*'s ``function.name`` → MCPTool, parse
        ``function.arguments``, execute the tool, and return a tool-role
        message dict suitable for appending to the LLM message history.

        Args:
            tool_call: An OpenAI-format tool call dict with ``id``,
                ``type``, and ``function`` (``name`` + ``arguments``).
            tenant_id: Tenant to scope the tool lookup under.
            db: Active database session.

        Returns:
            A dict with ``role``, ``tool_call_id``, and ``content``
            fields, ready to append to the LLM message list.
        """
        name = tool_call.get("function", {}).get("name", "")
        tool_call_id = tool_call.get("id", "")

        # ── Resolve tool name → MCPTool entry ────────────────────────────
        tool = await get_tool_by_name(db, name, tenant_id)
        if not tool or not tool.enabled:
            return {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": json.dumps({"error": f"Unknown tool: {name}"}),
            }

        # ── Parse arguments ──────────────────────────────────────────────
        try:
            params = json.loads(tool_call.get("function", {}).get("arguments", "{}"))
        except (json.JSONDecodeError, TypeError) as exc:
            return {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": json.dumps({"error": f"Invalid tool arguments: {exc}"}),
            }

        # ── Execute via MCP Gateway ──────────────────────────────────────
        try:
            result = await execute_tool(db, tool.id, params, tenant_id=tenant_id)
            content = result.get("result", result)
        except Exception as exc:
            logger.warning("Tool execution failed: %s — %s", name, exc)
            content = {"error": str(exc)}

        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": json.dumps(content, ensure_ascii=False, default=str),
        }

    # ── Batch Tool Execution ─────────────────────────────────────────────

    @staticmethod
    async def _execute_tool_calls(
        tool_calls: list[dict],
        tenant_id: int,
        db: AsyncSession,
    ) -> list[dict]:
        """Execute each *tool_call* from a single LLM response and collect
        the results as a list of tool-role message dicts.

        Each call is executed sequentially via ``_execute_single_tool``.
        """
        results: list[dict] = []
        for tc in tool_calls:
            result = await ToolRunner._execute_single_tool(tc, tenant_id, db)
            results.append(result)
        return results
