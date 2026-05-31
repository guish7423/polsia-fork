"""Test GET /api/v1/dashboard/* endpoints."""
import pytest


@pytest.mark.asyncio
async def test_get_summary(api_client, auth_headers):
    resp = await api_client.get("/api/v1/dashboard/summary", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "tasks_today_total" in data
    assert "mrr_cents" in data


@pytest.mark.asyncio
async def test_health_endpoint(api_client):
    resp = await api_client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
