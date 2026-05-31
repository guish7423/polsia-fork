"""Test GET /api/v1/finance/summary endpoint."""
import pytest
from datetime import date


@pytest.mark.asyncio
async def test_finance_summary_empty(api_client, auth_headers):
    """Returns zero values when no snapshot exists."""
    resp = await api_client.get("/api/v1/finance/summary", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["mrr_cents"] == 0
    assert data["arr_cents"] == 0
    assert data["active_subscribers"] == 0
    assert data["snapshot_date"] is None


@pytest.mark.asyncio
async def test_finance_summary_with_snapshot(api_client, auth_headers, async_db_session):
    """Returns values from the latest revenue snapshot."""
    from app.models.finance import RevenueSnapshot

    snap = RevenueSnapshot(
        snapshot_date=date.today(),
        mrr_cents=500000,
        arr_cents=6000000,
        active_subscribers=42,
        total_revenue_month_cents=150000,
    )
    async_db_session.add(snap)
    await async_db_session.commit()

    resp = await api_client.get("/api/v1/finance/summary", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["mrr_cents"] == 500000
    assert data["arr_cents"] == 6000000
    assert data["active_subscribers"] == 42



