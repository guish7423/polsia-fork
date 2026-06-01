"""External orders API — scan, evaluate, accept, fulfill."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import verify_api_key
from app.core.database import async_session
from app.services.order_deliverable_service import (
    generate_standard_deliverables,
    get_deliverables,
    save_deliverables,
)
from app.services.order_scanner_service import (
    create_order,
    get_orders,
    get_order,
    update_order_status,
    get_orders_summary,
    scan_platform,
)

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/orders/external")
async def list_external_orders(
    platform: str = Query("", description="Filter by platform"),
    status: str = Query("", description="Filter by status"),
    limit: int = Query(50, le=200),
):
    async with async_session() as db:
        data = await get_orders(db, platform or None, status or None, limit)
        return {"data": [format_order(o) for o in data], "total": len(data)}


@router.get("/orders/external/summary")
async def external_orders_summary():
    async with async_session() as db:
        return await get_orders_summary(db)


@router.post("/orders/external")
async def create_external_order(
    title: str,
    platform: str = "internal",
    external_id: str | None = None,
    budget_min: float | None = None,
    budget_max: float | None = None,
    currency: str = "USD",
    description: str | None = None,
    requirements: str | None = None,
    source_url: str | None = None,
):
    async with async_session() as db:
        order = await create_order(
            db, title, platform, external_id,
            budget_min, budget_max, currency,
            description, requirements, source_url,
        )
        await db.commit()
        return format_order(order)


@router.get("/orders/external/{order_id}")
async def get_external_order(order_id: int):
    async with async_session() as db:
        order = await get_order(db, order_id)
        if not order:
            raise HTTPException(404, "Order not found")
        return format_order(order)


@router.post("/orders/external/{order_id}/evaluate")
async def evaluate_order_endpoint(order_id: int):
    """Run AI evaluation on an order."""
    from app.agents.order_scanner import OrderScannerAgent

    async with async_session() as db:
        order = await get_order(db, order_id)
        if not order:
            raise HTTPException(404, "Order not found")
        agent = OrderScannerAgent()
        result = await agent.evaluate(db, order)
        return result


@router.post("/orders/external/{order_id}/accept")
async def accept_order(order_id: int, assigned_agent: str = ""):
    async with async_session() as db:
        order = await update_order_status(
            db, order_id, "accepted",
            assigned_agent=assigned_agent or None,
        )
        if not order:
            raise HTTPException(404, "Order not found")
        await db.commit()
        return format_order(order)


@router.post("/orders/external/{order_id}/demo-deploy")
async def demo_deploy_order(order_id: int):
    """Run DeployAgent on an order to generate a deployment plan (demo mode)."""
    from app.agents.deploy_agent import DeployAgent
    from app.models.external_order import ExternalOrder
    from sqlalchemy import select, update
    import json

    async with async_session() as db:
        order = await get_order(db, order_id)
        if not order:
            raise HTTPException(404, "Order not found")
        if order.assigned_agent != "deploy_agent":
            order.assigned_agent = "deploy_agent"

        agent = DeployAgent()
        plan = await agent.plan_deployment(db, order)
        # Persist plan to provider_notes for portal retrieval
        await db.execute(
            update(ExternalOrder).where(ExternalOrder.id == order_id)
            .values(provider_notes=json.dumps(plan, ensure_ascii=False))
        )
        await update_order_status(db, order_id, "in_progress")
        await db.commit()

        return {
            "order_id": order_id,
            "status": "in_progress",
            "plan": plan,
        }


@router.post("/orders/external/{order_id}/fulfill")
async def fulfill_order_endpoint(order_id: int):
    """Run AI fulfillment on an accepted order."""
    from app.agents.order_fulfiller import OrderFulfillerAgent

    async with async_session() as db:
        order = await get_order(db, order_id)
        if not order:
            raise HTTPException(404, "Order not found")
        agent = OrderFulfillerAgent()
        result = await agent._fulfill(db, order)
        await db.commit()
        return result


@router.get("/orders/external/{order_id}/deliverables")
async def get_order_deliverables(order_id: int):
    """Get deliverables for an order."""
    async with async_session() as db:
        order = await get_order(db, order_id)
        if not order:
            raise HTTPException(404, "Order not found")
        items = order.deliverables or []
        return {"order_id": order_id, "deliverables": items, "delivery_notes": order.delivery_notes}


@router.post("/orders/external/{order_id}/deliverables")
async def generate_order_deliverables(order_id: int):
    """Generate standard deliverables for an order (both accepted and completed)."""
    async with async_session() as db:
        order = await get_order(db, order_id)
        if not order:
            raise HTTPException(404, "Order not found")
        tier = "basic"
        combined = f"{order.description or ''} {order.requirements or ''}".lower()
        if "k8s" in combined or "kubernetes" in combined:
            tier = "enterprise"
        elif "postgres" in combined or "redis" in combined or "multi" in combined:
            tier = "standard"
        deliverables = generate_standard_deliverables(
            order_title=order.title,
            description=order.description or "",
            requirements=order.requirements or "",
            tier=tier,
            order_id=order.id,
        )
        result = await save_deliverables(db, order.id, deliverables, "Deliverables generated on-demand")
        await db.commit()
        return {"order_id": order_id, "deliverables": deliverables, **result}


@router.post("/orders/external/scan/{platform}")
async def scan_external_platform(platform: str):
    """Scan a platform for new orders."""
    valid = ("upwork", "fiverr", "zhubajie", "internal")
    if platform not in valid:
        raise HTTPException(400, f"Invalid platform. Choose: {', '.join(valid)}")
    async with async_session() as db:
        orders = await scan_platform(db, platform)
        await db.commit()
        return {"platform": platform, "new_orders": len(orders), "data": [format_order(o) for o in orders]}


def format_order(o) -> dict:
    return {
        "id": o.id,
        "title": o.title,
        "platform": o.platform,
        "external_id": o.external_id,
        "status": o.status,
        "budget_min": o.budget_min,
        "budget_max": o.budget_max,
        "currency": o.currency,
        "description": o.description,
        "requirements": o.requirements,
        "score": o.score,
        "score_reason": o.score_reason,
        "assigned_agent": o.assigned_agent,
        "source_url": o.source_url,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "updated_at": o.updated_at.isoformat() if o.updated_at else None,
        "completed_at": o.completed_at.isoformat() if o.completed_at else None,
        "deliverables": o.deliverables,
        "delivery_notes": o.delivery_notes,
    }
