"""Tests for auth — verify_api_key and verify_tenant."""

import pytest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException


@pytest.mark.asyncio
async def test_dev_api_key_works(monkeypatch):
    """Dev key should bypass tenant lookup."""
    monkeypatch.setattr("app.core.auth.settings.api_key", "dev-key")
    from app.core.auth import verify_api_key

    result = await verify_api_key(x_api_key="dev-key")
    assert result == "dev-key"


@pytest.mark.asyncio
async def test_valid_tenant_key(async_db_session, monkeypatch):
    """Valid tenant API key should be accepted."""
    monkeypatch.setattr("app.core.auth.settings.api_key", "dev-key")
    from app.core.auth import verify_api_key
    from app.services.tenant_service import create_tenant

    tenant = await create_tenant(async_db_session, name="TestCo", api_key="key_valid")

    with patch("app.core.auth.async_session") as mock_maker:
        mock_ctx = AsyncMock()
        mock_maker.return_value = mock_ctx
        mock_ctx.__aenter__.return_value = async_db_session
        mock_ctx.__aexit__.return_value = None

        result = await verify_api_key(x_api_key="key_valid")
        assert result == "key_valid"


@pytest.mark.asyncio
async def test_invalid_key_403(async_db_session, monkeypatch):
    """Invalid API key should raise 403."""
    monkeypatch.setattr("app.core.auth.settings.api_key", "dev-key")
    from app.core.auth import verify_api_key

    with patch("app.core.auth.async_session") as mock_maker:
        mock_ctx = AsyncMock()
        mock_maker.return_value = mock_ctx
        mock_ctx.__aenter__.return_value = async_db_session
        mock_ctx.__aexit__.return_value = None

        with pytest.raises(HTTPException) as exc:
            await verify_api_key(x_api_key="unknown")
        assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_inactive_key_403(async_db_session, monkeypatch):
    """Inactive tenant key should raise 403."""
    monkeypatch.setattr("app.core.auth.settings.api_key", "dev-key")
    from app.core.auth import verify_api_key
    from app.services.tenant_service import create_tenant

    tenant = await create_tenant(async_db_session, name="InactiveCo", api_key="key_inactive")
    tenant.active = False
    await async_db_session.flush()

    with patch("app.core.auth.async_session") as mock_maker:
        mock_ctx = AsyncMock()
        mock_maker.return_value = mock_ctx
        mock_ctx.__aenter__.return_value = async_db_session
        mock_ctx.__aexit__.return_value = None

        with pytest.raises(HTTPException) as exc:
            await verify_api_key(x_api_key="key_inactive")
        assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_verify_tenant_returns_context(async_db_session, monkeypatch):
    """verify_tenant should return a TenantContext."""
    monkeypatch.setattr("app.core.auth.settings.api_key", "dev-key")
    from app.core.auth import verify_tenant
    from app.services.tenant_service import create_tenant

    await create_tenant(async_db_session, name="Acme", api_key="key_acme")

    with patch("app.core.auth.async_session") as mock_maker:
        mock_ctx = AsyncMock()
        mock_maker.return_value = mock_ctx
        mock_ctx.__aenter__.return_value = async_db_session
        mock_ctx.__aexit__.return_value = None

        ctx = await verify_tenant(x_api_key="key_acme")
        assert ctx.name == "Acme"
        assert ctx.plan == "starter"
        assert ctx.active is True


@pytest.mark.asyncio
async def test_verify_tenant_dev_key(monkeypatch):
    """Dev key should return enterprise-level context."""
    monkeypatch.setattr("app.core.auth.settings.api_key", "dev-key")
    from app.core.auth import verify_tenant

    ctx = await verify_tenant(x_api_key="dev-key")
    assert ctx.name == "Development"
    assert ctx.plan == "enterprise"
    assert ctx.active is True


@pytest.mark.asyncio
async def test_verify_tenant_invalid_key(async_db_session, monkeypatch):
    """Invalid key should raise 403."""
    monkeypatch.setattr("app.core.auth.settings.api_key", "dev-key")
    from app.core.auth import verify_tenant

    with patch("app.core.auth.async_session") as mock_maker:
        mock_ctx = AsyncMock()
        mock_maker.return_value = mock_ctx
        mock_ctx.__aenter__.return_value = async_db_session
        mock_ctx.__aexit__.return_value = None

        with pytest.raises(HTTPException) as exc:
            await verify_tenant(x_api_key="unknown")
        assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_verify_api_key_keeps_str_signature(monkeypatch):
    """verify_api_key still returns str (backward compat)."""
    monkeypatch.setattr("app.core.auth.settings.api_key", "dev-key")
    from app.core.auth import verify_api_key

    result = await verify_api_key(x_api_key="dev-key")
    assert isinstance(result, str)
