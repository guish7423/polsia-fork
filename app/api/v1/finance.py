"""Finance API routes — revenue, expenses, and Stripe integration."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import verify_api_key
from app.core.database import get_db
from app.models.finance import ExpenseRecord, RevenueSnapshot
from app.models.stripe import StripeEvent

router = APIRouter(tags=["finance"])


@router.get("/finance/summary")
async def get_finance_summary(
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Get finance summary with latest snapshot and expense totals."""
    latest = (
        await db.execute(
            select(RevenueSnapshot)
            .order_by(RevenueSnapshot.snapshot_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    total_expenses = (
        await db.execute(
            select(func.coalesce(func.sum(ExpenseRecord.amount_cents), 0))
        )
    ).scalar() or 0

    if latest:
        return {
            "mrr_cents": latest.mrr_cents,
            "arr_cents": latest.arr_cents,
            "total_expenses_cents": total_expenses,
            "total_revenue_cents": latest.total_revenue_month_cents,
            "active_subscribers": latest.active_subscribers,
            "last_snapshot_date": latest.snapshot_date.isoformat() if latest.snapshot_date else None,
        }
    return {
        "mrr_cents": 0,
        "arr_cents": 0,
        "total_expenses_cents": total_expenses,
        "total_revenue_cents": 0,
        "active_subscribers": 0,
        "last_snapshot_date": None,
    }


@router.get("/finance/revenue")
async def list_revenue_snapshots(
    limit: int = 100,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """List revenue snapshots, most recent first."""
    result = await db.execute(
        select(RevenueSnapshot).order_by(RevenueSnapshot.snapshot_date.desc()).limit(limit)
    )
    return [
        {
            "id": s.id,
            "snapshot_date": s.snapshot_date.isoformat() if s.snapshot_date else None,
            "mrr_cents": s.mrr_cents,
            "arr_cents": s.arr_cents,
            "total_revenue_month_cents": s.total_revenue_month_cents,
            "stripe_balance_cents": s.stripe_balance_cents,
            "active_subscribers": s.active_subscribers,
        }
        for s in result.scalars().all()
    ]


@router.get("/finance/expenses")
async def list_expenses(
    category: str | None = None,
    limit: int = 100,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """List expense records with optional category filter."""
    query = select(ExpenseRecord).order_by(ExpenseRecord.date.desc()).limit(limit)
    if category:
        query = query.where(ExpenseRecord.category == category)
    result = await db.execute(query)
    return [
        {
            "id": e.id,
            "category": e.category,
            "vendor": e.vendor,
            "amount_cents": e.amount_cents,
            "currency": e.currency,
            "description": e.description,
            "date": e.date.isoformat() if e.date else None,
        }
        for e in result.scalars().all()
    ]


@router.get("/finance/events")
async def list_stripe_events(
    limit: int = 100,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """List Stripe events."""
    result = await db.execute(
        select(StripeEvent).order_by(StripeEvent.processed_at.desc()).limit(limit)
    )
    return [
        {
            "id": e.id,
            "stripe_event_id": e.stripe_event_id,
            "event_type": e.event_type,
            "status": e.status,
        }
        for e in result.scalars().all()
    ]


@router.post("/finance/stripe/webhook")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle Stripe webhook events."""
    from app.config import settings

    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=500, detail="Stripe webhook secret not configured")

    body = await request.body()
    signature = request.headers.get("stripe-signature", "")

    try:
        import hashlib
        import hmac

        expected_sig = hmac.new(
            settings.stripe_webhook_secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()

        # Parse signature header
        header_parts = {}
        for part in signature.split(","):
            if "=" in part:
                k, v = part.split("=", 1)
                header_parts[k.strip()] = v.strip()

        if header_parts.get("v1", "") != expected_sig:
            raise HTTPException(status_code=400, detail="Invalid signature")

        # Store event
        import json
        payload = json.loads(body)
        event = StripeEvent(
            stripe_event_id=payload.get("id", "unknown"),
            event_type=payload.get("type", "unknown"),
            status="received",
        )
        db.add(event)
        await db.flush()
        return {"status": "received", "event_id": event.stripe_event_id}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
