"""Standalone ``call_llm_with_tools()`` — multi-round LLM + tool execution.

This module provides function-calling capability to Polsia agents via
``ModelInstance.chat()``.  It is intentionally a standalone function
(rather than a base-class method) so it can be used, tested, and evolved
independently from the agent class hierarchy.

Design
------
- Uses ``ModelInstance.chat()`` directly (not ``call_llm()``) because it
  accepts ``messages: list[dict]`` and passes ``**kwargs`` (including
  ``tools`` and ``tool_choice``) through to the provider.
- ``json_mode`` is ``False`` during tool-calling rounds (OpenAI API rejects
  ``response_format=json_object`` + ``tools`` in the same request).  The
  final round re-enables JSON parsing on the response content.
- Tool-call history is maintained in the local ``messages`` list across
  rounds so the LLM sees the full conversation context.
- ``ToolRunner._execute_single_tool()`` handles name → ID resolution and
  result formatting.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.core.model_instance import TaskCategory
from app.services.model_router import (
    agent_category,
    select_instance,
)
from app.services.tool_runner import ToolRunner

logger = logging.getLogger(__name__)


async def call_llm_with_tools(
    *,
    agent_type: str,
    task_category: TaskCategory | None = None,
    prompt: str,
    system_prompt: str | None = None,
    max_tool_rounds: int = 5,
    task_category_override: TaskCategory | None = None,
    db_session=None,
    tenant_id: int | None = None,
) -> dict[str, Any]:
    """Multi-round LLM call with tool execution via ``ModelInstance.chat()``.

    Parameters
    ----------
    agent_type : str
        The agent type (used to derive task category when not specified).
    task_category : TaskCategory | None
        Agent's default task category (falls back to ``agent_category()``
        lookup if ``None``).
    prompt : str
        The user query / instruction.
    system_prompt : str | None
        Optional system-level instruction prepended to the message list.
    max_tool_rounds : int
        Maximum number of LLM + tool-execution rounds (default 5).
    task_category_override : TaskCategory | None
        Override the task category for this specific call (takes precedence
        over both *task_category* and *agent_type*).
    db_session : optional
        Database session for tool execution.
    tenant_id : int | None
        Tenant scope for tool lookups.  When ``None``, no tools are loaded
        and the function acts like a plain ``call_llm()``.

    Returns
    -------
    dict
        Either ``{"result": <str>}`` for plain content, or the parsed JSON
        dict on the final round, or ``{"result": …, "_tool_rounds": N}``
        when the round limit is hit.
    """
    # ── Load tool definitions ─────────────────────────────────────────────
    tools: list[dict] = []
    if tenant_id is not None and db_session is not None:
        tools = await ToolRunner._build_tools_defs(tenant_id, db_session)

    # ── Select model instance ─────────────────────────────────────────────
    category = task_category_override or task_category or agent_category(agent_type)
    model_instance = select_instance(category)
    if model_instance is None:
        return {"result": "fallback", "error": "No LLM instance available for this category"}

    # ── Build initial messages ────────────────────────────────────────────
    messages: list[dict[str, Any]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    # ── Multi-round loop ─────────────────────────────────────────────────
    for _round in range(max_tool_rounds):
        is_json_round = _round == max_tool_rounds - 1  # only final round expects JSON

        # Build kwargs for this round.
        # json_mode=False during tool rounds; the final round uses JSON parsing
        # on the returned content instead.
        kwargs: dict[str, Any] = {"temperature": 0.7, "json_mode": False}
        if not is_json_round and tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            result = await model_instance.chat(
                messages=messages,
                **kwargs,
            )
        except Exception as exc:
            logger.exception("call_llm_with_tools chat() failed: %s", exc)
            return {"result": "error", "error": str(exc)}

        # ── Parse the response ────────────────────────────────────────────
        raw = result.raw or {}
        choices = raw.get("choices", [])
        if not choices:
            # Non-OpenAI format or empty response — return content as-is
            return {"result": result.content}

        msg = choices[0].get("message", {})
        tool_calls = msg.get("tool_calls")

        if not tool_calls:
            # No more tool calls — return the final content
            content = msg.get("content", "")
            try:
                parsed = json.loads(content)
                # When json parsing succeeds on the final round, return
                # the parsed dict directly (matching call_llm behavior)
                if isinstance(parsed, dict):
                    return parsed
                return {"result": parsed}
            except (json.JSONDecodeError, TypeError):
                return {"result": content}

        # ── Execute tool calls and append results ─────────────────────────
        messages.append({
            "role": "assistant",
            "content": msg.get("content"),
            "tool_calls": tool_calls,
        })
        # Tool calls are only present when tools were loaded, which requires
        # db_session.  Assert to keep mypy happy.
        assert db_session is not None
        for tc in tool_calls:
            tool_result = await ToolRunner._execute_single_tool(
                tc, tenant_id or 0, db_session,
            )
            messages.append(tool_result)

    # ── Max rounds reached — return aggregated ────────────────────────────
    return {"result": messages[-1].get("content", ""), "_tool_rounds": max_tool_rounds}
