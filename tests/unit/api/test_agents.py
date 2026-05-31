"""Test POST /api/v1/agents/{type}/trigger and GET /api/v1/agents."""
import pytest


@pytest.mark.asyncio
async def test_list_agents(api_client, auth_headers):
    resp = await api_client.get("/api/v1/agents", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 9
    agent_types = [a["agent_type"] for a in data]
    assert "social_media" in agent_types
    assert "finance" in agent_types


@pytest.mark.asyncio
async def test_trigger_valid_agent(api_client, auth_headers):
    resp = await api_client.post(
        "/api/v1/agents/social_media/trigger",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "message" in data
    assert "social_media" in data["message"]


@pytest.mark.asyncio
async def test_trigger_invalid_agent(api_client, auth_headers):
    resp = await api_client.post(
        "/api/v1/agents/nonexistent/trigger",
        headers=auth_headers,
    )
    assert resp.status_code == 404



