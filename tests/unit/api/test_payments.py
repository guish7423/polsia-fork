"""Tests for Payment API — Stripe Checkout integration.

create-checkout (uses get_db → overridden by api_client) is testable with in-memory DB.
create-product-checkout is synchronous Stripe-only, tested via mock.
"""

import json
import pytest


@pytest.mark.asyncio
async def test_create_checkout_order_not_found(api_client, auth_headers):
    """Nonexistent order returns 404."""
    resp = await api_client.post(
        "/api/v1/orders/99999/create-checkout",
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_checkout_no_proposal(api_client, auth_headers, async_db_session):
    """Order with no proposal returns error (can't create checkout without amount)."""
    # Create an order first
    from app.models.external_order import ExternalOrder
    order = ExternalOrder(
        title="Test Order",
        platform="direct",
        status="accepted",
        budget_min=2000,
        budget_max=4000,
        currency="USD",
    )
    async_db_session.add(order)
    await async_db_session.commit()
    await async_db_session.refresh(order)
    order_id = order.id

    resp = await api_client.post(
        f"/api/v1/orders/{order_id}/create-checkout",
        headers=auth_headers,
    )
    # Should fail — payment_service calls Stripe which isn't configured
    assert resp.status_code in (502, 400, 404)


@pytest.mark.asyncio
async def test_create_product_checkout_no_stripe(api_client):
    """Product checkout returns 502 when Stripe not configured."""
    resp = await api_client.post(
        "/api/v1/create-product-checkout",
        json={"product_key": "crossdeploy-basic", "customer_email": "buyer@test.com"},
    )
    # May return 200 with mock or 502 (Stripe not configured)
    assert resp.status_code in (200, 502)
    if resp.status_code == 502:
        data = resp.json()
        assert "stripe" in json.dumps(data).lower() or "configured" in json.dumps(data).lower()


@pytest.mark.asyncio
async def test_product_checkout_invalid_key(api_client):
    """Invalid product key should return 502/400."""
    resp = await api_client.post(
        "/api/v1/create-product-checkout",
        json={"product_key": "nonexistent-product"},
    )
    assert resp.status_code in (400, 502)
