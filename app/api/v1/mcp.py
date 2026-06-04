"""MCP Gateway API — register, list, execute MCP tools."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.tenant_context import get_current_tenant
from app.services.mcp_gateway import (
    ToolNotFound,
    execute_tool,
    get_tool,
    get_tool_by_name,
    list_tools,
    register_tool,
    unregister_tool,
)

router = APIRouter(prefix="/mcp", tags=["mcp"])


# ─── Tenant ID dependency ────────────────────────────────────────────────


async def _get_tenant_id() -> int:
    """Extract tenant ID from the current request context."""
    tenant = get_current_tenant()
    if tenant is None:
        raise HTTPException(status_code=401, detail="Tenant context not found — provide a valid X-API-Key header")
    return tenant.id


# ─── Request / Response schemas ───────────────────────────────────────────


class RegisterToolRequest(BaseModel):
    name: str
    description: str = ""
    endpoint: str
    tool_schema: dict = Field(default={}, alias="schema")
    auth_config: dict | None = None
    enabled: bool = True
    cache_ttl_seconds: int = 0
    timeout_seconds: int = 30


class ExecuteRequest(BaseModel):
    params: dict = {}


class ExecuteByNameRequest(BaseModel):
    tool_name: str
    params: dict = {}


# ─── Endpoints ────────────────────────────────────────────────────────────


@router.post("/tools")
async def api_register_tool(
    body: RegisterToolRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(_get_tenant_id),
):
    """Register a new MCP tool."""
    tool = await register_tool(
        db,
        tenant_id=tenant_id,
        name=body.name,
        description=body.description,
        endpoint=body.endpoint,
        schema_json=body.tool_schema,
        auth_config=body.auth_config,
        enabled=body.enabled,
        cache_ttl_seconds=body.cache_ttl_seconds,
        timeout_seconds=body.timeout_seconds,
    )
    return {
        "id": tool.id,
        "name": tool.name,
        "description": tool.description,
        "endpoint": tool.endpoint,
        "enabled": tool.enabled,
    }


@router.get("/tools")
async def api_list_tools(
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(_get_tenant_id),
):
    """List all tools for the current tenant."""
    tools = await list_tools(db, tenant_id)
    return [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "endpoint": t.endpoint,
            "enabled": t.enabled,
        }
        for t in tools
    ]


@router.get("/tools/{tool_id}")
async def api_get_tool(
    tool_id: int,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(_get_tenant_id),
):
    """Get details for a specific tool."""
    tool = await get_tool(db, tool_id, tenant_id)
    if not tool:
        raise HTTPException(404, "Tool not found")
    return {
        "id": tool.id,
        "name": tool.name,
        "description": tool.description,
        "endpoint": tool.endpoint,
        "enabled": tool.enabled,
    }


@router.delete("/tools/{tool_id}")
async def api_unregister_tool(
    tool_id: int,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(_get_tenant_id),
):
    """Unregister a tool."""
    removed = await unregister_tool(db, tenant_id, tool_id)
    if not removed:
        raise HTTPException(404, "Tool not found")
    return {"status": "deleted"}


@router.post("/tools/{tool_id}/execute")
async def api_execute_tool(
    tool_id: int,
    body: ExecuteRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(_get_tenant_id),
):
    """Execute a registered tool by ID."""
    try:
        result = await execute_tool(
            db, tool_id, body.params, tenant_id=tenant_id
        )
        return result
    except ToolNotFound:
        raise HTTPException(404, "Tool not found or disabled")


@router.post("/execute-by-name")
async def api_execute_by_name(
    body: ExecuteByNameRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(_get_tenant_id),
):
    """Execute a registered tool by name (agent-friendly)."""
    tool = await get_tool_by_name(db, body.tool_name, tenant_id)
    if not tool or not tool.enabled:
        raise HTTPException(404, f"Tool '{body.tool_name}' not found or disabled")
    try:
        result = await execute_tool(
            db, tool.id, body.params, tenant_id=tenant_id
        )
        return result
    except ToolNotFound:
        raise HTTPException(404, f"Tool '{body.tool_name}' not found or disabled")
