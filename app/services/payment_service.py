"""Payment service — Stripe Checkout integration for the Quick Quote pipeline.

Creates a Stripe Checkout Session when a customer accepts a proposal,
and handles the checkout.session.completed webhook to trigger fulfillment.
"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.external_order import ExternalOrder

logger = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────


def _stripe_available() -> bool:
    """Check if Stripe is configured."""
    return bool(settings.stripe_secret_key)


def _get_stripe():
    """Lazy-import stripe and set the API key."""
    import stripe as stripe_lib

    stripe_lib.api_key = settings.stripe_secret_key
    return stripe_lib


# ── Public API ───────────────────────────────────────────────────────────


# ── Product catalog for direct-buy ──────────────────────────────────────

PRODUCT_CATALOG = {
    "crossdeploy-basic": {
        "name": "CrossDeploy Basic",
        "description": "Single service deployment with custom domain + HTTPS + monitoring",
        "amount_cents": 200000,  # ¥2,000
        "currency": "cny",
    },
    "crossdeploy-standard": {
        "name": "CrossDeploy Standard",
        "description": "Multi-service deployment with Docker Compose + CI/CD + 30d support",
        "amount_cents": 300000,  # ¥3,000
        "currency": "cny",
    },
    "crossdeploy-enterprise": {
        "name": "CrossDeploy Enterprise",
        "description": "Full-stack K8s deployment with auto-scaling + SLA",
        "amount_cents": 500000,  # ¥5,000
        "currency": "cny",
    },
}


def create_product_checkout(
    product_key: str,
    customer_email: str,
    success_url: str,
    cancel_url: str,
) -> dict | None:
    """Create a Stripe Checkout Session for a direct product purchase.

    This is for the pricing page "Buy Now" flow — no order or proposal needed.

    Args:
        product_key: Product identifier (e.g. 'crossdeploy-basic')
        customer_email: Customer's email for pre-fill
        success_url: Redirect URL on successful payment
        cancel_url: Redirect URL on cancelled payment

    Returns:
        dict with session_id, url, or None if Stripe not configured.
    """
    if not _stripe_available():
        logger.warning("Stripe not configured — skipping product checkout")
        return None

    product = PRODUCT_CATALOG.get(product_key)
    if not product:
        logger.warning(f"Unknown product key: {product_key}")
        return None

    # Check if a Stripe Price ID is configured for this product
    price_id = settings.stripe_price_lookup.get(product_key, "")

    try:
        stripe = _get_stripe()
        line_items = []

        if price_id:
            line_items.append({"price": price_id, "quantity": 1})
        else:
            line_items.append({
                "price_data": {
                    "currency": product["currency"],
                    "product_data": {
                        "name": product["name"],
                        "description": product["description"],
                    },
                    "unit_amount": product["amount_cents"],
                },
                "quantity": 1,
            })

        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=line_items,
            customer_email=customer_email or None,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"product_key": product_key, "source": "direct-buy"},
        )

        return {
            "session_id": session.id,
            "url": session.url,
            "amount_total": session.amount_total,
            "currency": session.currency,
        }
    except Exception as e:
        logger.error(f"Failed to create product checkout session: {e}")
        return None


def create_checkout_session(
    order_id: int,
    tier: str,
    customer_email: str,
    success_url: str,
    cancel_url: str,
    proposed_amount_cents: int | None = None,
) -> dict | None:
    """Create a Stripe Checkout Session for an accepted proposal.

    Args:
        order_id: ExternalOrder ID
        tier: Pricing tier (basic/standard/enterprise)
        customer_email: Customer's email for pre-fill
        success_url: Redirect URL on successful payment
        cancel_url: Redirect URL on cancelled payment
        proposed_amount_cents: Override amount in cents. If None, uses price_lookup.

    Returns:
        dict with session_id, url, or None if Stripe not configured.
    """
    if not _stripe_available():
        logger.warning("Stripe not configured — skipping checkout session creation")
        return None

    try:
        stripe = _get_stripe()
        line_items = []

        if proposed_amount_cents:
            # Use custom amount (from proposal)
            line_items.append({
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": f"CrossWave Deploy — {tier.title()}",
                        "description": f"CrossWave Deployment Service ({tier.title()} tier)",
                    },
                    "unit_amount": proposed_amount_cents,
                },
                "quantity": 1,
            })
        else:
            # Use predefined price ID from settings
            price_id = settings.stripe_price_lookup.get(tier)
            if not price_id:
                logger.warning(f"No Stripe price_id configured for tier '{tier}'")
                return None
            line_items.append({"price": price_id, "quantity": 1})

        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=line_items,
            customer_email=customer_email,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"order_id": str(order_id), "tier": tier},
            payment_intent_data={
                "metadata": {"order_id": str(order_id)},
            },
        )

        return {
            "session_id": session.id,
            "url": session.url,
            "amount_total": session.amount_total,
            "currency": session.currency,
        }
    except Exception as e:
        logger.error(f"Failed to create Stripe Checkout session: {e}")
        return None


async def update_order_payment(
    db: AsyncSession,
    order_id: int,
    stripe_session_id: str,
    amount_paid_cents: int,
    payment_status: str = "pending",
) -> None:
    """Record Stripe session info on an order."""
    await db.execute(
        update(ExternalOrder)
        .where(ExternalOrder.id == order_id)
        .values(
            stripe_session_id=stripe_session_id,
            payment_status=payment_status,
            amount_paid=amount_paid_cents / 100.0,
        )
    )
    await db.flush()


async def handle_checkout_completed(
    db: AsyncSession,
    session_id: str,
    order_id: int,
    amount_total: int,
) -> dict:
    """Handle checkout.session.completed webhook.

    Marks order as paid and updates payment details.
    Returns the updated order dict.
    """
    now = datetime.now(timezone.utc)

    await db.execute(
        update(ExternalOrder)
        .where(ExternalOrder.id == order_id)
        .values(
            payment_status="paid",
            stripe_session_id=session_id,
            amount_paid=amount_total / 100.0,
        )
    )
    await db.flush()

    # Fetch updated order
    result = await db.execute(
        select(ExternalOrder).where(ExternalOrder.id == order_id)
    )
    order = result.scalar_one_or_none()
    return {
        "order_id": order_id,
        "payment_status": "paid",
        "amount_paid": amount_total / 100.0,
    }
