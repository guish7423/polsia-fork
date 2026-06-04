"""Tests for MCP Gateway — tool registration, execution, tenant isolation, and audit logging."""

from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.mcp_tool import MCPTool
from app.models.mcp_tool_call import MCPToolCall


async def _register_tool(db, tenant_id: int = 1, name: str = "web_search",
                         endpoint: str = "https://httpbin.org/post",
                         schema_json: dict | None = None) -> MCPTool:
    from app.services.mcp_gateway import register_tool
    return await register_tool(
        db, tenant_id=tenant_id, name=name, description="Test tool",
        endpoint=endpoint, schema_json=schema_json or {},
    )


# ─── Model / Service Tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_register_mcp_tool(async_db_session):
    """Register a tool and verify it has an ID."""
    tool = await _register_tool(async_db_session, tenant_id=1, name="web_search",
                                 schema_json={"input": {"type": "object", "properties": {"q": {"type": "string"}}}})
    assert tool.id is not None
    assert tool.name == "web_search"
    assert tool.tenant_id == 1


@pytest.mark.asyncio
async def test_execute_mcp_tool(async_db_session, mocker):
    """HTTP POST to registered endpoint and return result."""
    mock_client = mocker.patch("app.services.mcp_gateway.MCPClient")
    mock_instance = mock_client.return_value
    mock_instance.call_tool = AsyncMock(return_value={"result": "mocked"})

    tool = await _register_tool(async_db_session, tenant_id=1, name="echo")
    from app.services.mcp_gateway import execute_tool
    result = await execute_tool(async_db_session, tool.id, {"test": "data"}, timeout=15)
    assert "result" in result
    assert isinstance(result["result"], dict)


@pytest.mark.asyncio
async def test_mcp_tool_isolated_by_tenant(async_db_session):
    """Tools must be isolated by tenant."""
    from app.services.mcp_gateway import register_tool as reg, list_tools
    t1 = await reg(async_db_session, tenant_id=1, name="x", description="", endpoint="https://example.com/x", schema_json={})
    await reg(async_db_session, tenant_id=2, name="x", description="", endpoint="https://example.com/x", schema_json={})
    tools_t1 = await list_tools(async_db_session, tenant_id=1)
    assert len(tools_t1) == 1
    assert tools_t1[0].id == t1.id


@pytest.mark.asyncio
async def test_execute_unknown_tool_returns_404(async_db_session):
    """Executing a non-existent tool raises ToolNotFound."""
    from app.services.mcp_gateway import execute_tool, ToolNotFound
    with pytest.raises(ToolNotFound):
        await execute_tool(async_db_session, 99999, {})


@pytest.mark.asyncio
async def test_mcp_tool_call_logged(async_db_session, mocker):
    """Every execution creates an MCPToolCall record for audit."""
    # Mock the HTTP client to avoid real network calls
    mock_client = mocker.patch("app.services.mcp_gateway.MCPClient")
    mock_instance = mock_client.return_value
    mock_instance.call_tool = AsyncMock(return_value={"mock": "result"})

    tool = await _register_tool(async_db_session, tenant_id=1, name="audit-check")
    from app.services.mcp_gateway import execute_tool
    await execute_tool(async_db_session, tool.id, {"ping": "pong"}, timeout=15)

    result = await async_db_session.execute(
        select(MCPToolCall).where(MCPToolCall.tool_id == tool.id)
    )
    call = result.scalar_one_or_none()
    assert call is not None
    assert call.success is True
    assert call.duration_ms >= 0


# ─── API Route Tests ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_api_register_tool(api_client, auth_headers):
    """POST /api/v1/mcp/tools — register a new tool."""
    resp = await api_client.post(
        "/api/v1/mcp/tools",
        json={
            "name": "web_search",
            "description": "Search the web",
            "endpoint": "https://api.example.com/mcp/search",
            "schema": {"input": {"type": "object", "properties": {"q": {"type": "string"}}}},
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "web_search"
    assert data["id"] is not None


@pytest.mark.asyncio
async def test_api_list_tools(api_client, auth_headers):
    """GET /api/v1/mcp/tools — list tenant-scoped tools."""
    # Register two tools
    await api_client.post("/api/v1/mcp/tools", json={"name": "a", "description": "", "endpoint": "https://a.com", "schema": {}}, headers=auth_headers)
    await api_client.post("/api/v1/mcp/tools", json={"name": "b", "description": "", "endpoint": "https://b.com", "schema": {}}, headers=auth_headers)

    resp = await api_client.get("/api/v1/mcp/tools", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


@pytest.mark.asyncio
async def test_api_get_tool(api_client, auth_headers):
    """GET /api/v1/mcp/tools/{id} — get tool details."""
    create = await api_client.post("/api/v1/mcp/tools", json={"name": "detail-test", "description": "x", "endpoint": "https://x.com", "schema": {}}, headers=auth_headers)
    tool_id = create.json()["id"]

    resp = await api_client.get(f"/api/v1/mcp/tools/{tool_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "detail-test"


@pytest.mark.asyncio
async def test_api_unregister_tool(api_client, auth_headers):
    """DELETE /api/v1/mcp/tools/{id} — unregister a tool."""
    create = await api_client.post("/api/v1/mcp/tools", json={"name": "delete-me", "description": "", "endpoint": "https://x.com", "schema": {}}, headers=auth_headers)
    tool_id = create.json()["id"]

    resp = await api_client.delete(f"/api/v1/mcp/tools/{tool_id}", headers=auth_headers)
    assert resp.status_code == 200

    # Verify it's gone
    get_resp = await api_client.get(f"/api/v1/mcp/tools/{tool_id}", headers=auth_headers)
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_api_execute_tool(api_client, auth_headers, mocker):
    """POST /api/v1/mcp/tools/{id}/execute — invoke a tool."""
    mocker.patch("app.services.mcp_gateway.MCPClient.call_tool", return_value={"mocked": "result"})
    create = await api_client.post("/api/v1/mcp/tools", json={"name": "exec-test", "description": "", "endpoint": "https://httpbin.org/post", "schema": {}}, headers=auth_headers)
    tool_id = create.json()["id"]

    resp = await api_client.post(
        f"/api/v1/mcp/tools/{tool_id}/execute",
        json={"params": {"test": "data"}},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "result" in data


@pytest.mark.asyncio
async def test_api_execute_by_name(api_client, auth_headers, mocker):
    """POST /api/v1/mcp/execute-by-name — agent-friendly execution."""
    mocker.patch("app.services.mcp_gateway.MCPClient.call_tool", return_value={"mocked": "result"})
    await api_client.post("/api/v1/mcp/tools", json={"name": "by-name", "description": "", "endpoint": "https://httpbin.org/post", "schema": {}}, headers=auth_headers)

    resp = await api_client.post(
        "/api/v1/mcp/execute-by-name",
        json={"tool_name": "by-name", "params": {"hello": "world"}},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert "result" in resp.json()


@pytest.mark.asyncio
async def test_api_mcp_404_on_unknown_tool(api_client, auth_headers):
    """Executing a non-existent tool via API returns 404."""
    resp = await api_client.post(
        "/api/v1/mcp/tools/99999/execute",
        json={"params": {}},
        headers=auth_headers,
    )
    assert resp.status_code == 404
