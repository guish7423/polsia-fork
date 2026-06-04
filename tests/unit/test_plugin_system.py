"""Tests for Plugin System v1 — registration, hooks, tenant isolation."""

import pytest
from unittest.mock import AsyncMock

from app.models.plugin import Plugin


async def _register_plugin(db, tenant_id: int = 1, name: str = "audit-logger",
                         webhook_url: str = "https://hooks.example.com/audit",
                         manifest: dict | None = None) -> Plugin:
    from app.services.plugin_registry import register_plugin
    return await register_plugin(
        db, tenant_id=tenant_id, name=name,
        description="Test plugin",
        webhook_url=webhook_url,
        manifest=manifest or {"version": "1.0", "hooks": ["after_agent_run"]},
    )


# ─── Model / Service Tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_register_plugin(async_db_session):
    """Register a plugin with manifest + webhook_url and verify it has an ID."""
    plugin = await _register_plugin(async_db_session, tenant_id=1, name="audit-logger")
    assert plugin.id is not None
    assert plugin.name == "audit-logger"
    assert plugin.enabled is True
    assert plugin.webhook_url == "https://hooks.example.com/audit"


@pytest.mark.asyncio
async def test_plugin_enable_disable(async_db_session):
    """Toggle enabled state on a registered plugin."""
    from app.services.plugin_registry import register_plugin, set_plugin_enabled, get_plugin

    plugin = await register_plugin(
        async_db_session, tenant_id=1, name="toggle-test",
        description="", webhook_url="https://example.com/hook",
        manifest={"version": "1.0", "hooks": ["after_agent_run"]},
    )

    # Disable
    await set_plugin_enabled(async_db_session, plugin.id, False, tenant_id=1)
    p = await get_plugin(async_db_session, plugin.id, tenant_id=1)
    assert p is not None
    assert p.enabled is False

    # Re-enable
    await set_plugin_enabled(async_db_session, plugin.id, True, tenant_id=1)
    p = await get_plugin(async_db_session, plugin.id, tenant_id=1)
    assert p is not None
    assert p.enabled is True


@pytest.mark.asyncio
async def test_hook_invocation_calls_webhook(async_db_session, mocker):
    """call_hooks() sends POST to webhook_url of all matching enabled plugins."""
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    await _register_plugin(async_db_session, tenant_id=1, name="logger",
                           webhook_url="https://hooks.example.com/logger",
                           manifest={"version": "1.0", "hooks": ["after_agent_run"]})

    from app.services.plugin_registry import call_hooks
    results = await call_hooks(async_db_session, tenant_id=1,
                               hook_name="after_agent_run",
                               context={"run_id": 42})

    assert len(results) == 1
    assert results[0]["plugin"] == "logger"
    assert results[0]["status"] == 200

    # Verify POST was called with correct payload
    call_kwargs = mock_post.call_args
    assert call_kwargs is not None
    sent_json = call_kwargs.kwargs["json"]
    assert sent_json["hook"] == "after_agent_run"
    assert sent_json["context"]["run_id"] == 42


@pytest.mark.asyncio
async def test_plugin_isolated_by_tenant(async_db_session):
    """Plugins belonging to different tenants must not leak."""
    from app.services.plugin_registry import register_plugin as reg, list_plugins

    t1 = await reg(async_db_session, tenant_id=1, name="x",
                   description="", webhook_url="https://ex.com/x",
                   manifest={"version": "1.0", "hooks": ["after_agent_run"]})
    await reg(async_db_session, tenant_id=2, name="x",
              description="", webhook_url="https://ex.com/x",
              manifest={"version": "1.0", "hooks": ["after_agent_run"]})

    plugins_t1 = await list_plugins(async_db_session, tenant_id=1)
    assert len(plugins_t1) == 1
    assert plugins_t1[0].id == t1.id


@pytest.mark.asyncio
async def test_disabled_plugin_not_called(async_db_session, mocker):
    """Disabled plugins should not receive hook callbacks."""
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    from app.services.plugin_registry import register_plugin, set_plugin_enabled, call_hooks

    plugin = await register_plugin(
        async_db_session, tenant_id=1, name="disabled-logger",
        description="", webhook_url="https://hooks.example.com/dlogger",
        manifest={"version": "1.0", "hooks": ["after_agent_run"]},
    )

    # Disable before calling hooks
    await set_plugin_enabled(async_db_session, plugin.id, False, tenant_id=1)

    results = await call_hooks(async_db_session, tenant_id=1,
                               hook_name="after_agent_run",
                               context={"run_id": 99})
    assert len(results) == 0
    mock_post.assert_not_called()


@pytest.mark.asyncio
async def test_hook_timeout_doesnt_block(async_db_session, mocker):
    """Webhook timeout should not block the main flow — error is captured."""
    mock_post = mocker.patch("httpx.AsyncClient.post")
    mock_post.side_effect = TimeoutError("Connection timed out")

    await _register_plugin(async_db_session, tenant_id=1, name="timeout-plugin",
                           webhook_url="https://slow.example.com/hook",
                           manifest={"version": "1.0", "hooks": ["after_agent_run"]})

    from app.services.plugin_registry import call_hooks
    results = await call_hooks(async_db_session, tenant_id=1,
                               hook_name="after_agent_run",
                               context={"run_id": 100})

    # Should complete without raising and capture the error
    assert len(results) == 1
    assert results[0]["plugin"] == "timeout-plugin"
    assert "error" in results[0]


@pytest.mark.asyncio
async def test_unregister_plugin(async_db_session):
    """Unregister a plugin and verify it's gone."""
    from app.services.plugin_registry import register_plugin, unregister_plugin, get_plugin

    plugin = await register_plugin(
        async_db_session, tenant_id=1, name="delete-me",
        description="", webhook_url="https://ex.com/hook",
        manifest={"version": "1.0", "hooks": ["after_agent_run"]},
    )

    await unregister_plugin(async_db_session, plugin.id, tenant_id=1)
    p = await get_plugin(async_db_session, plugin.id, tenant_id=1)
    assert p is None


# ─── Hook Definitions Tests ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_hook_definitions_are_known():
    """HOOK_DEFINITIONS contains all expected extension points."""
    from app.core.plugin_hooks import HOOK_DEFINITIONS

    assert "before_agent_run" in HOOK_DEFINITIONS
    assert "after_agent_run" in HOOK_DEFINITIONS
    assert "on_agent_error" in HOOK_DEFINITIONS
    assert "before_tool_call" in HOOK_DEFINITIONS


# ─── API Route Tests ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_api_register_plugin(api_client, auth_headers):
    """POST /api/v1/plugins — register a new plugin."""
    resp = await api_client.post(
        "/api/v1/plugins",
        json={
            "name": "audit-logger",
            "description": "Audit all agent runs",
            "webhook_url": "https://hooks.example.com/audit",
            "manifest": {"version": "1.0", "hooks": ["after_agent_run"]},
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "audit-logger"
    assert data["id"] is not None
    assert data["enabled"] is True


@pytest.mark.asyncio
async def test_api_list_plugins(api_client, auth_headers):
    """GET /api/v1/plugins — list tenant-scoped plugins."""
    await api_client.post("/api/v1/plugins", json={
        "name": "p1", "description": "", "webhook_url": "https://a.com/hook",
        "manifest": {"version": "1.0", "hooks": ["after_agent_run"]},
    }, headers=auth_headers)
    await api_client.post("/api/v1/plugins", json={
        "name": "p2", "description": "", "webhook_url": "https://b.com/hook",
        "manifest": {"version": "1.0", "hooks": ["after_agent_run"]},
    }, headers=auth_headers)

    resp = await api_client.get("/api/v1/plugins", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


@pytest.mark.asyncio
async def test_api_get_plugin(api_client, auth_headers):
    """GET /api/v1/plugins/{id} — get plugin details."""
    create = await api_client.post("/api/v1/plugins", json={
        "name": "detail-test", "description": "x",
        "webhook_url": "https://x.com/hook",
        "manifest": {"version": "1.0", "hooks": ["after_agent_run"]},
    }, headers=auth_headers)
    pid = create.json()["id"]

    resp = await api_client.get(f"/api/v1/plugins/{pid}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "detail-test"


@pytest.mark.asyncio
async def test_api_patch_plugin(api_client, auth_headers):
    """PATCH /api/v1/plugins/{id} — enable/disable or update config."""
    create = await api_client.post("/api/v1/plugins", json={
        "name": "patch-test", "description": "",
        "webhook_url": "https://x.com/hook",
        "manifest": {"version": "1.0", "hooks": ["after_agent_run"]},
    }, headers=auth_headers)
    pid = create.json()["id"]

    # Disable it
    resp = await api_client.patch(f"/api/v1/plugins/{pid}", json={
        "enabled": False,
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False

    # Re-enable it
    resp = await api_client.patch(f"/api/v1/plugins/{pid}", json={
        "enabled": True,
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True


@pytest.mark.asyncio
async def test_api_delete_plugin(api_client, auth_headers):
    """DELETE /api/v1/plugins/{id} — unregister a plugin."""
    create = await api_client.post("/api/v1/plugins", json={
        "name": "delete-me", "description": "",
        "webhook_url": "https://x.com/hook",
        "manifest": {"version": "1.0", "hooks": ["after_agent_run"]},
    }, headers=auth_headers)
    pid = create.json()["id"]

    resp = await api_client.delete(f"/api/v1/plugins/{pid}", headers=auth_headers)
    assert resp.status_code == 200

    # Verify gone
    get_resp = await api_client.get(f"/api/v1/plugins/{pid}", headers=auth_headers)
    assert get_resp.status_code == 404
