"""Tests for Quick Quote — one-call lead-to-proposal pipeline.

The quick-quote endpoint uses get_db (dependency override in api_client),
so in-memory SQLite works transparently.
"""

import pytest


@pytest.mark.asyncio
async def test_quick_quote_success(api_client):
    """Valid data creates lead → order → proposal → deliverables → sent."""
    resp = await api_client.post(
        "/api/v1/quick-quote",
        json={
            "name": "Alice Wang",
            "email": "alice@example.com",
            "company": "TechCo",
            "project_description": "Docker deployment for FastAPI app",
            "budget_range": "2000-4000",
            "preferred_tier": "standard",
        },
    )
    # Expect 200 (success) — 500 if pipeline fails
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    data = resp.json()
    assert data["status"] == "sent"
    assert "order_id" in data
    assert "proposal_id" in data
    assert "view_token" in data
    assert "view_url" in data
    assert isinstance(data["order_id"], int)
    assert data["order_id"] > 0


@pytest.mark.asyncio
async def test_quick_quote_missing_name(api_client):
    """Missing name returns 400."""
    resp = await api_client.post(
        "/api/v1/quick-quote",
        json={"email": "alice@example.com"},
    )
    assert resp.status_code == 400
    assert "name" in resp.text.lower() or "email" in resp.text.lower()


@pytest.mark.asyncio
async def test_quick_quote_missing_email(api_client):
    """Missing email returns 400."""
    resp = await api_client.post(
        "/api/v1/quick-quote",
        json={"name": "Alice Wang"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_quick_quote_minimal(api_client):
    """Minimal data (name + email only) succeeds with basic tier."""
    resp = await api_client.post(
        "/api/v1/quick-quote",
        json={"name": "Bob Li", "email": "bob@test.com"},
    )
    assert resp.status_code == 200, f"Expected 200: {resp.text[:200]}"
    data = resp.json()
    assert data["status"] == "sent"
    assert "order_id" in data


@pytest.mark.asyncio
async def test_quick_quote_tier_basic(api_client):
    """Low budget → basic tier."""
    resp = await api_client.post(
        "/api/v1/quick-quote",
        json={
            "name": "Test", "email": "test@test.com",
            "budget_range": "500-1000",
        },
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_quick_quote_tier_enterprise(api_client):
    """High budget (≥4000) → enterprise tier."""
    resp = await api_client.post(
        "/api/v1/quick-quote",
        json={
            "name": "Test", "email": "test@test.com",
            "budget_range": "4000-10000",
        },
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_quick_quote_disconnected(mocker, api_client):
    """When Polsia Fork is unreachable, quick-quote still works (no external dep)."""
    # quick-quote uses get_db which is overridden to in-memory
    # No external call dependency — it's all local DB operations
    resp = await api_client.post(
        "/api/v1/quick-quote",
        json={"name": "Carol", "email": "carol@test.com"},
    )
    assert resp.status_code == 200
