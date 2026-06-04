"""MCP Gateway — tool registration, listing, and execution service."""

from __future__ import annotations

import json
import logging
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.mcp_client import MCPClient
from app.models.mcp_tool import MCPTool
from app.models.mcp_tool_call import MCPToolCall

logger = logging.getLogger(__name__)


class ToolNotFound(Exception):
    """Raised when a requested tool does not exist or is disabled."""


async def register_tool(
    db: AsyncSession,
    tenant_id: int,
    name: str,
    description: str,
    endpoint: str,
    schema_json: dict | None = None,
    auth_config: dict | None = None,
    enabled: bool = True,
    cache_ttl_seconds: int = 0,
    timeout_seconds: int = 30,
) -> MCPTool:
    """Register a new MCP tool for the given *tenant_id*."""
    tool = MCPTool(
        tenant_id=tenant_id,
        name=name,
        description=description,
        endpoint=endpoint,
        schema_json=schema_json or {},
        auth_config=auth_config,
        enabled=enabled,
        cache_ttl_seconds=cache_ttl_seconds,
        timeout_seconds=timeout_seconds,
    )
    db.add(tool)
    await db.flush()
    await db.refresh(tool)
    return tool


async def unregister_tool(db: AsyncSession, tenant_id: int, tool_id: int) -> bool:
    """Remove a tool. Returns True if the tool existed and was removed."""
    result = await db.execute(
        select(MCPTool).where(MCPTool.id == tool_id, MCPTool.tenant_id == tenant_id)
    )
    tool = result.scalar_one_or_none()
    if not tool:
        return False
    await db.delete(tool)
    await db.flush()
    return True


async def get_tool(
    db: AsyncSession, tool_id: int, tenant_id: int
) -> MCPTool | None:
    """Get a single tool by ID, scoped to *tenant_id*."""
    result = await db.execute(
        select(MCPTool).where(MCPTool.id == tool_id, MCPTool.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def get_tool_by_name(
    db: AsyncSession, name: str, tenant_id: int
) -> MCPTool | None:
    """Get a single tool by name, scoped to *tenant_id*."""
    result = await db.execute(
        select(MCPTool).where(MCPTool.name == name, MCPTool.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def list_tools(db: AsyncSession, tenant_id: int) -> list[MCPTool]:
    """List all tools for the given *tenant_id*."""
    result = await db.execute(
        select(MCPTool)
        .where(MCPTool.tenant_id == tenant_id)
        .order_by(MCPTool.id)
    )
    return list(result.scalars().all())


async def execute_tool(
    db: AsyncSession,
    tool_id: int,
    params: dict,
    agent_run_id: int | None = None,
    tenant_id: int | None = None,
    timeout: int | None = None,
) -> dict:
    """Execute a registered MCP tool and log the call.

    Args:
        db: Database session.
        tool_id: ID of the registered tool.
        params: Parameters to send to the tool endpoint.
        agent_run_id: Optional agent run ID for auditing.
        tenant_id: Tenant ID for scoping. If None, will be read from the tool.
        timeout: Override the tool's default timeout.

    Returns:
        The JSON result from the tool endpoint.

    Raises:
        ToolNotFound: If the tool does not exist or is disabled.
    """
    # Resolve the tool
    if tenant_id is not None:
        tool = await get_tool(db, tool_id, tenant_id)
    else:
        result = await db.execute(select(MCPTool).where(MCPTool.id == tool_id))
        tool = result.scalar_one_or_none()
        if tool:
            tenant_id = tool.tenant_id

    if not tool or not tool.enabled:
        raise ToolNotFound(f"Tool {tool_id} not found or disabled")

    client = MCPClient()
    actual_timeout = timeout or tool.timeout_seconds or 30
    start = time.monotonic()

    try:
        result_data = await client.call_tool(
            tool.endpoint, params, tool.auth_config, actual_timeout
        )
        success = True
        error_msg = None
        output_summary = _truncate_json(result_data, 500)
    except Exception as exc:
        result_data = {"error": str(exc)}
        success = False
        error_msg = str(exc)
        output_summary = None

    duration_ms = int((time.monotonic() - start) * 1000)

    # Log the call
    call = MCPToolCall(
        tool_id=tool.id,
        tenant_id=tenant_id,
        agent_run_id=agent_run_id,
        input_params=params,
        output_summary=output_summary,
        duration_ms=duration_ms,
        success=success,
        error_message=error_msg,
        cost_usd=0.0,
    )
    db.add(call)
    await db.flush()

    return {"result": result_data}


def _truncate_json(data: dict, max_chars: int = 500) -> str:
    """JSON-serialise *data*, truncating to *max_chars*."""
    text = json.dumps(data, ensure_ascii=False, default=str)
    if len(text) > max_chars:
        text = text[:max_chars] + "..."
    return text
