"""Payment API — Stripe Checkout integration.

POST /create-product-checkout     — Direct product purchase (pricing page "Buy Now")
POST /orders/{id}/create-checkout — Create Stripe session for a proposal
POST /stripe/webhook              — Stripe webhook handler (raw body)
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db
from app.models.external_order import ExternalOrder
from app.services.payment_service import (
    create_checkout_session,
    handle_checkout_completed,
    update_order_payment,
)
from app.services.proposal_service import get_proposals_for_order
from app.services.order_scanner_service import get_order

logger = logging.getLogger(__name__)

router = APIRouter(tags=["payments"])

# Public router — no API key (needed for Stripe webhook + checkout redirects)
payment_router = APIRouter(tags=["payments-public"])


@payment_router.post("/create-product-checkout")
async def create_product_checkout(data: dict):
    """Direct product purchase from pricing page — no order/proposal needed.

    Body:
        product_key (str): e.g. 'crossdeploy-basic'
        customer_email (str, optional)
        success_url (str, optional)
        cancel_url (str, optional)

    Returns Stripe Checkout URL for redirect.
    """
    from app.services.payment_service import create_product_checkout as svc

    product_key = data.get("product_key", "")
    customer_email = data.get("customer_email", "")
    base = settings.base_url.rstrip("/")
    success_url = data.get("success_url", f"{base}/?payment=success")
    cancel_url = data.get("cancel_url", f"{base}/?payment=cancelled")

    result = svc(product_key, customer_email, success_url, cancel_url)
    if not result:
        raise HTTPException(502, "Failed to create checkout. Stripe may not be configured.")

    return {
        "checkout_url": result["url"],
        "session_id": result["session_id"],
        "amount_total": result["amount_total"] / 100,
        "currency": result["currency"],
    }


@payment_router.post("/orders/{order_id}/create-checkout")
async def create_checkout(order_id: int, db: AsyncSession = Depends(get_db)):
    """Create a Stripe Checkout Session for an accepted proposal.

    The proposal must be in 'won' status (customer accepted).
    Returns the Stripe Checkout URL for redirect.
    """
    # Verify order exists
    order = await get_order(db, order_id)
    if not order:
        raise HTTPException(404, "Order not found")

    if order.payment_status in ("paid", "processing"):
        raise HTTPException(400, f"Order payment is already {order.payment_status}")

    if order.execution_status == "completed":
        raise HTTPException(400, "Order already completed")

    # Find the won proposal for this order
    proposals = await get_proposals_for_order(db, order_id)
    won_proposal = None
    for p in proposals:
        if p.status == "won":
            won_proposal = p
            break

    if not won_proposal:
        raise HTTPException(400, "No accepted proposal found for this order. Accept the proposal first.")

    # Determine tier & amount
    tier = "standard"
    if order.budget_min and order.budget_max:
        mid = (order.budget_min + order.budget_max) / 2
        if mid >= 4000:
            tier = "enterprise"
        elif mid >= 2000:
            tier = "standard"
        else:
            tier = "basic"
    elif order.provider_notes:
        # Try to extract tier from notes
        for t in ("enterprise", "standard", "basic"):
            if t in order.provider_notes.lower():
                tier = t
                break

    # Amount in cents from proposal
    proposed_amount_cents = None
    if won_proposal.proposed_amount:
        proposed_amount_cents = int(won_proposal.proposed_amount * 100)

    # Build redirect URLs
    base = settings.base_url
    customer_email = order.customer_email or ""

    session_data = create_checkout_session(
        order_id=order_id,
        tier=tier,
        customer_email=customer_email,
        success_url=f"{base}/quote/{won_proposal.view_token}?payment=success",
        cancel_url=f"{base}/quote/{won_proposal.view_token}?payment=cancelled",
        proposed_amount_cents=proposed_amount_cents,
    )

    if not session_data:
        raise HTTPException(502, "Failed to create payment session. Stripe may not be configured.")

    # Save session info to order
    await update_order_payment(
        db, order_id, session_data["session_id"],
        session_data["amount_total"], "pending"
    )
    await db.commit()

    return {
        "checkout_url": session_data["url"],
        "session_id": session_data["session_id"],
        "amount_total": session_data["amount_total"] / 100,
        "currency": session_data["currency"],
    }


@payment_router.post("/stripe/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Stripe webhook events — primarily checkout.session.completed."""
    import stripe  # noqa: F811 — lazy import for webhook signature verification

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not settings.stripe_webhook_secret:
        logger.warning("STRIPE_WEBHOOK_SECRET not configured — accepting raw event")
        event = json.loads(payload)
    else:
        try:
            stripe.api_key = settings.stripe_secret_key
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.stripe_webhook_secret
            )
        except ValueError:
            raise HTTPException(400, "Invalid payload")
        except stripe.error.SignatureVerificationError:
            raise HTTPException(400, "Invalid signature")

    event_type = event.get("type", event.get("type", ""))
    logger.info(f"Stripe webhook received: {event_type}")

    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        order_id = int(session.get("metadata", {}).get("order_id", 0))
        amount_total = session.get("amount_total", 0)
        session_id = session.get("id", "")

        if order_id:
            await handle_checkout_completed(db, session_id, order_id, amount_total)
            await db.commit()

            # Trigger fulfillment (import here to avoid circular)
            try:
                from app.agents.deploy_agent import DeployAgent
                from sqlalchemy import select, update as sql_update
                import json as json_mod

                result = await db.execute(
                    select(ExternalOrder).where(ExternalOrder.id == order_id)
                )
                order = result.scalar_one_or_none()
                if order:
                    agent = DeployAgent()
                    plan = await agent.plan_deployment(db, order)
                    await db.execute(
                        sql_update(ExternalOrder)
                        .where(ExternalOrder.id == order_id)
                        .values(provider_notes=json_mod.dumps(plan, ensure_ascii=False))
                    )
                    await db.commit()

                    # Send customer notification
                    from app.services.email_service import send_deliverables_ready
                    view_url = f"{settings.base_url}/quote/{event.get('data', {}).get('object', {}).get('metadata', {}).get('view_token', '')}"

                    # Find the proposal view_token
                    from app.models.proposal import Proposal
                    proposals_res = await db.execute(
                        select(Proposal).where(Proposal.order_id == order_id).order_by(Proposal.created_at.desc()).limit(1)
                    )
                    latest_proposal = proposals_res.scalar_one_or_none()
                    if latest_proposal:
                        view_url = f"{settings.base_url}/quote/{latest_proposal.view_token}"
                        if order.customer_email:
                            send_deliverables_ready(
                                name=order.customer_email.split("@")[0],
                                email=order.customer_email,
                                view_url=view_url,
                                order_title=order.title or "Deployment",
                            )

            except Exception as e:
                logger.error(f"Auto-fulfillment after payment failed (non-blocking): {e}")

        return {"status": "ok", "event": event_type}

    elif event_type == "checkout.session.expired":
        session = event["data"]["object"]
        order_id = int(session.get("metadata", {}).get("order_id", 0))
        if order_id:
            await db.execute(
                __import__("sqlalchemy").update(ExternalOrder)
                .where(ExternalOrder.id == order_id)
                .values(payment_status="expired")
            )
            await db.commit()
        return {"status": "ok", "event": event_type}

    return {"status": "ignored", "event": event_type}
