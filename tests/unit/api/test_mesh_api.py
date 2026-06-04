"""Test mesh API endpoints."""

import pytest
from unittest.mock import patch

from app.services.mesh_bus import send_message


class TestMeshListMessages:
    @pytest.mark.asyncio
    async def test_list_messages_empty(self, api_client, auth_headers):
        resp = await api_client.get("/api/v1/mesh/messages", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "messages" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_list_messages_with_filter(self, api_client, auth_headers, async_db_session):
        # Create a message first (tenant_id=0 matches TenantContextMiddleware test key)
        await send_message(
            async_db_session, 0, "orchestrator",
            "delegation", "Post update",
            recipient_type="social_media",
        )
        resp = await api_client.get(
            "/api/v1/mesh/messages?agent_type=social_media",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert data["messages"][0]["recipient_type"] == "social_media"


class TestMeshSendMessage:
    @pytest.mark.asyncio
    async def test_send_message(self, api_client, auth_headers):
        resp = await api_client.post(
            "/api/v1/mesh/messages?sender_type=orchestrator&recipient_type=social_media&title=Hello&message_type=generic",
            headers=auth_headers,
            json={"body": {"text": "hello"}},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "sent"
        assert "message_id" in data


class TestMeshMessageLifecycle:
    @pytest.mark.asyncio
    async def test_mark_delivered(self, api_client, auth_headers, async_db_session):
        msg = await send_message(
            async_db_session, 0, "a",
            "generic", "test",
            recipient_type="b",
        )
        resp = await api_client.post(
            f"/api/v1/mesh/messages/{msg.id}/deliver",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "delivered"

    @pytest.mark.asyncio
    async def test_mark_read(self, api_client, auth_headers, async_db_session):
        msg = await send_message(
            async_db_session, 0, "a",
            "generic", "test",
            recipient_type="b",
        )
        resp = await api_client.post(
            f"/api/v1/mesh/messages/{msg.id}/read",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "read"


class TestMeshCapabilities:
    @pytest.mark.asyncio
    async def test_list_capabilities(self, api_client, auth_headers):
        resp = await api_client.get(
            "/api/v1/mesh/capabilities",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "capabilities" in data
        assert "web_search" in data["capabilities"]

    @pytest.mark.asyncio
    async def test_filter_capability(self, api_client, auth_headers):
        resp = await api_client.get(
            "/api/v1/mesh/capabilities?capability=financial_analysis",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["capability"] == "financial_analysis"


class TestMeshPending:
    @pytest.mark.asyncio
    async def test_get_pending(self, api_client, auth_headers, async_db_session):
        await send_message(
            async_db_session, 0, "a",
            "delegation", "Task 1",
            recipient_type="social_media",
        )
        resp = await api_client.get(
            "/api/v1/mesh/pending?agent_type=social_media",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_type"] == "social_media"
        assert data["total"] >= 1


class TestMeshErrors:
    @pytest.mark.asyncio
    async def test_get_nonexistent_message(self, api_client, auth_headers):
        resp = await api_client.get(
            "/api/v1/mesh/messages/99999",
            headers=auth_headers,
        )
        assert resp.status_code == 404
