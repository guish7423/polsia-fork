"""Billing API routes — Stripe checkout, portal, webhook, and plans."""
from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.billing_service import (
    create_checkout_session,
    create_portal_session,
    handle_webhook,
    process_webhook_event,
)
from app.services.plans import list_plans

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/plans")
async def get_plans():
    """List all available plans with pricing."""
    return list_plans()


@router.post("/create-checkout")
async def checkout(
    email: str,
    plan: str = "starter",
    interval: str = "month",
    success_url: str = "https://polsia.app/dashboard",
    cancel_url: str = "https://polsia.app/pricing",
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Checkout Session for new subscription."""
    url = await create_checkout_session(
        db, email=email, plan_name=plan,
        interval=interval, success_url=success_url, cancel_url=cancel_url,
    )
    return {"checkout_url": url}


@router.post("/portal")
async def billing_portal(
    email: str,
    return_url: str = "https://polsia.app/settings",
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Customer Portal session."""
    url = await create_portal_session(db, email=email, return_url=return_url)
    if not url:
        return {"error": "No active subscription found"}
    return {"portal_url": url}


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(default="", alias="stripe-signature"),
):
    """Stripe webhook endpoint — receives subscription lifecycle events."""
    payload = await request.body()
    result = await handle_webhook(payload, stripe_signature)
    return result
