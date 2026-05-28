"""Billing service — Stripe subscription management."""
import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings


def _get_stripe():
    """Lazy import Stripe to allow mock in tests."""
    import stripe
    stripe.api_key = settings.stripe_secret_key
    return stripe
    stripe.api_key = settings.stripe_api_key

async def create_checkout_session(
    db: AsyncSession,
    company_id: int,
    price_id: str | None = None,
    success_url: str = "https://polsia.app/dashboard",
    cancel_url: str = "https://polsia.app/pricing",
) -> str:
    """Create a Stripe Checkout Session for subscription."""
    from app.models.subscription import Subscription

    stripe = _get_stripe()

    # Create/update subscription record
    result = await db.execute(
        select(Subscription).where(Subscription.company_id == company_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        sub = Subscription(
            company_id=company_id,
            status="pending",
            trial_end=datetime.now(timezone.utc) + timedelta(days=14),
        )
        db.add(sub)
        await db.flush()

    session = stripe.checkout.Session.create(
        mode="subscription" if price_id else "setup",
        customer=sub.stripe_customer_id or None,
        line_items=[{"price": price_id, "quantity": 1}] if price_id else None,
        metadata={"company_id": str(company_id), "sub_id": str(sub.id)},
        success_url=success_url,
        cancel_url=cancel_url,
    )
    return session.url


async def handle_webhook(payload: bytes, sig_header: str) -> dict:
    """Verify and process Stripe webhook events."""
    stripe = _get_stripe()
    event = stripe.Webhook.construct_event(
        payload, sig_header, settings.stripe_webhook_secret
    )
    return {"type": event.type, "status": "received"}


def register_free_tier(company_name: str, email: str) -> dict:
    """Register company for free trial and generate API key."""
    return {
        "company_name": company_name,
        "email": email,
        "api_key": secrets.token_hex(16),
        "trial_days": 14,
        "plan": "free",
    }


async def verify_subscription(db: AsyncSession, company_id: int) -> dict:
    """Check if company has an active subscription."""
    from app.models.subscription import Subscription

    result = await db.execute(
        select(Subscription).where(
            Subscription.company_id == company_id,
            Subscription.status.in_(["active", "trialing"]),
        )
    )
    sub = result.scalar_one_or_none()
    return {
        "active": sub is not None,
        "status": sub.status if sub else "none",
    }
