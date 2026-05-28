"""Billing service — Stripe subscription management with full lifecycle."""

import json
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging import get_logger
from app.models.subscription import Subscription
from app.services.plans import get_plan, get_plan_from_price_id, PLANS

logger = get_logger(__name__)


def _get_stripe():
    """Lazy import Stripe to allow mock in tests."""
    import stripe as stripe_lib
    stripe_lib.api_key = settings.stripe_api_key
    return stripe_lib


async def create_checkout_session(
    db: AsyncSession,
    email: str,
    plan_name: str = "starter",
    interval: str = "month",
    success_url: str = "https://polsia.app/dashboard",
    cancel_url: str = "https://polsia.app/pricing",
) -> str:
    """Create a Stripe Checkout Session for new subscription."""
    plan = get_plan(plan_name)
    if not plan:
        raise ValueError(f"Unknown plan: {plan_name}")

    price_id = plan.stripe_price_id_monthly if interval == "month" else plan.stripe_price_id_yearly
    if not price_id:
        raise ValueError(f"No Stripe price configured for plan={plan_name} interval={interval}")

    stripe = _get_stripe()

    # Find or create customer
    result = await db.execute(
        select(Subscription).where(Subscription.email == email)
    )
    sub = result.scalar_one_or_none()

    customer_id = None
    metadata: dict = {}
    if sub:
        customer_id = sub.stripe_customer_id or None
        metadata = {"sub_id": str(sub.id), "email": email}

    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        customer_email=email if not customer_id else None,
        line_items=[{"price": price_id, "quantity": 1}],
        metadata=metadata,
        success_url=success_url,
        cancel_url=cancel_url,
        subscription_data={
            "metadata": metadata,
        },
    )

    return session.url


async def create_portal_session(
    db: AsyncSession,
    email: str,
    return_url: str = "https://polsia.app/settings",
) -> str | None:
    """Create a Stripe Customer Portal session for managing subscription."""
    result = await db.execute(
        select(Subscription).where(Subscription.email == email)
    )
    sub = result.scalar_one_or_none()
    if not sub or not sub.stripe_customer_id:
        return None

    stripe = _get_stripe()
    session = stripe.billing_portal.Session.create(
        customer=sub.stripe_customer_id,
        return_url=return_url,
    )
    return session.url


async def handle_webhook(payload: bytes, sig_header: str) -> dict:
    """Verify and process Stripe webhook events."""
    stripe = _get_stripe()
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except ValueError:
        logger.warning("stripe_webhook_invalid_payload")
        return {"status": "error", "message": "Invalid payload"}
    except stripe.error.SignatureVerificationError:
        logger.warning("stripe_webhook_invalid_signature")
        return {"status": "error", "message": "Invalid signature"}

    event_type = event.type
    logger.info("stripe_webhook_received", extra={"type": event_type})

    # We handle the event asynchronously via a lightweight handler
    return {
        "status": "received",
        "type": event_type,
        "event_id": event.id,
    }


async def process_webhook_event(
    db: AsyncSession,
    event_type: str,
    event_data: dict,
) -> dict:
    """Process a Stripe webhook event — update subscription state."""
    from app.models.stripe import StripeEvent

    stripe_event_id = event_data.get("id", "unknown")

    # Deduplicate
    existing = await db.execute(
        select(StripeEvent).where(
            StripeEvent.stripe_event_id == stripe_event_id
        )
    )
    if existing.scalar_one_or_none():
        return {"status": "ignored", "reason": "duplicate"}

    # Store raw event
    db_event = StripeEvent(
        stripe_event_id=stripe_event_id,
        event_type=event_type,
        status="processing",
        raw_data=json.dumps(event_data),
    )
    db.add(db_event)
    await db.flush()

    result = {"event_id": stripe_event_id, "type": event_type}

    # Handle specific event types
    if event_type.startswith("customer.subscription."):
        sub_data = event_data.get("data", {}).get("object", {})
        customer_email = (
            sub_data.get("metadata", {}).get("email")
            or _get_customer_email(sub_data.get("customer"))
        )
        stripe_sub_id = sub_data.get("id")
        price_id = sub_data.get("items", {}).get("data", [{}])[0].get("price", {}).get("id", "")
        status = sub_data.get("status", "unknown")

        if customer_email:
            # Find or create subscription record
            db_result = await db.execute(
                select(Subscription).where(Subscription.email == customer_email)
            )
            sub = db_result.scalar_one_or_none()

            if sub:
                plan = get_plan_from_price_id(price_id) or get_plan("starter")
                plan_name = plan.name if plan else "starter"

                if event_type == "customer.subscription.deleted":
                    sub.status = "canceled"
                    sub.active = False
                    result["action"] = "canceled"
                elif status == "active":
                    sub.status = "active"
                    sub.active = True
                    sub.stripe_subscription_id = stripe_sub_id
                    sub.stripe_price_id = price_id
                    sub.plan = plan_name
                    sub.agents_limit = plan.agents_limit if plan else sub.agents_limit
                    sub.tasks_monthly_limit = plan.tasks_monthly_limit if plan else sub.tasks_monthly_limit
                    period_start = sub_data.get("current_period_start")
                    period_end = sub_data.get("current_period_end")
                    if period_start:
                        sub.current_period_start = datetime.fromtimestamp(period_start, tz=timezone.utc)
                    if period_end:
                        sub.current_period_end = datetime.fromtimestamp(period_end, tz=timezone.utc)
                    result["action"] = "activated"
                elif status == "past_due":
                    sub.status = "past_due"
                    result["action"] = "past_due"
                elif status in ("incomplete", "incomplete_expired"):
                    sub.status = status
                    result["action"] = status

    elif event_type == "checkout.session.completed":
        session_data = event_data.get("data", {}).get("object", {})
        customer_email = session_data.get("customer_email") or session_data.get("customer_details", {}).get("email")
        customer_id = session_data.get("customer")
        sub_id = session_data.get("subscription")

        if customer_email and customer_id:
            db_result = await db.execute(
                select(Subscription).where(Subscription.email == customer_email)
            )
            sub = db_result.scalar_one_or_none()
            if sub:
                sub.stripe_customer_id = customer_id
                if sub_id:
                    sub.stripe_subscription_id = sub_id
                sub.status = "pending"
                result["action"] = "checkout_completed"

    # Mark event as processed
    db_event.status = "processed" if result.get("action") else "ignored"

    logger.info(
        "stripe_webhook_processed",
        extra={"type": event_type, "action": result.get("action", "none")},
    )

    return result


def _get_customer_email(customer_id: str | None) -> str | None:
    """Fetch customer email from Stripe (fallback)."""
    if not customer_id:
        return None
    try:
        stripe_obj = _get_stripe()
        customer = stripe_obj.Customer.retrieve(customer_id)
        return customer.get("email")
    except Exception:
        return None


def register_free_tier(email: str, company_name: str = "My Company") -> dict:
    """Register company for free trial and generate API key."""
    plan = get_plan("free")
    return {
        "company_name": company_name,
        "email": email,
        "api_key": secrets.token_hex(16),
        "plan": "free",
        "agents_limit": plan.agents_limit if plan else 3,
        "tasks_monthly_limit": plan.tasks_monthly_limit if plan else 100,
    }


async def verify_usage_limits(
    db: AsyncSession,
    api_key: str,
    agent_type: str | None = None,
    task_count: int = 1,
) -> dict:
    """Verify company hasn't exceeded plan limits. Returns {'allowed': bool, 'reason': str}."""
    result = await db.execute(
        select(Subscription).where(Subscription.api_key == api_key)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        return {"allowed": True}

    if not sub.active and sub.status not in ("trialing", "active", "free"):
        return {"allowed": False, "reason": "Subscription inactive"}

    # Check agent limit
    if agent_type and sub.agents_limit:
        from app.models.agent_run import AgentRun
        from sqlalchemy import func as sa_func

        agent_count = (
            await db.execute(
                select(sa_func.count()).select_from(AgentRun).where(
                    AgentRun.agent_type == agent_type,
                    AgentRun.status == "running",
                )
            )
        ).scalar() or 0

        if agent_count >= sub.agents_limit:
            return {"allowed": False, "reason": f"Agent limit reached ({sub.agents_limit})"}

    return {"allowed": True}
