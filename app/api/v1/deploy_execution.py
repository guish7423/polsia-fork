"""Deploy Execution API — trigger, status, and logs for deployment execution."""

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import verify_api_key
from app.core.database import async_session
from app.models.external_order import ExternalOrder
from app.services import deploy_execution_engine as engine
from app.services.order_deliverable_service import get_deliverables
from app.services.email_service import send_deliverables_ready, send_internal_notification
from app.config import settings

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.post("/orders/external/{order_id}/execute-deploy")
async def execute_deploy(order_id: int):
    """Trigger deployment execution for an order.

    Reads deliverables from DB, writes files to staging directory,
    creates git repo and .tar.gz archive.
    """
    async with async_session() as db:
        from sqlalchemy import select
        result = await db.execute(
            select(ExternalOrder).where(ExternalOrder.id == order_id)
        )
        order = result.scalar_one_or_none()
        if not order:
            raise HTTPException(404, "Order not found")
        if order.status not in ("accepted", "in_progress", "completed"):
            raise HTTPException(400, f"Order status '{order.status}' cannot be deployed")

        deliverables = await get_deliverables(db, order_id)
        if not deliverables:
            raise HTTPException(400, "No deliverables found for this order")

        # Detect tier from existing data
        tier = "basic"
        combined = (order.description or "") + (order.requirements or "")
        if "k8s" in combined or "kubernetes" in combined or "enterprise" in combined:
            tier = "enterprise"
        elif "postgres" in combined or "redis" in combined or "multi" in combined or "standard" in combined:
            tier = "standard"

        result = await engine.execute_deploy(
            order_id=order_id,
            deliverables=deliverables,
            tier=tier,
            project_title=order.title,
        )

        # Store execution status in DB
        from sqlalchemy import update
        await db.execute(
            update(ExternalOrder)
            .where(ExternalOrder.id == order_id)
            .values(
                execution_status=result["state"],
                deploy_dir=result.get("deploy_dir"),
            )
        )

        # Send notification if execution completed successfully
        if result.get("state") == "completed":
            view_url = f"{settings.base_url}/quote/{order_id}"
            if order.customer_email:
                # Derive customer name from requirements
                customer_name = order.title or "Customer"
                if order.requirements and order.requirements.startswith("Client: "):
                    customer_name = order.requirements.split("<")[0].replace("Client: ", "").strip()
                send_deliverables_ready(
                    customer_name, order.customer_email, view_url, order.title or "部署服务"
                )
            send_internal_notification(
                "Deliverables Ready ✅",
                f"Order #{order_id} ({order.title}) — {result.get('file_count', 0)} files, {result.get('archive_size', 'N/A')}",
                view_url,
            )

        await db.commit()

    return result


@router.get("/orders/external/{order_id}/execution-status")
async def get_execution_status(order_id: int):
    """Get deployment execution status for an order."""
    status = engine.get_status(order_id)

    # Check DB for persisted state
    async with async_session() as db:
        from sqlalchemy import select
        result = await db.execute(
            select(ExternalOrder.execution_status, ExternalOrder.deploy_dir)
            .where(ExternalOrder.id == order_id)
        )
        row = result.first()
        if row:
            status["db_execution_status"] = row[0]
            status["db_deploy_dir"] = row[1]

    return status
