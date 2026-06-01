"""Order Fulfiller Agent — auto-fulfills accepted external orders."""

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BasePolsiaAgent, register_agent
from app.agents.prompts import ORDER_FULFILLER_SYSTEM_PROMPT
from app.models.external_order import ExternalOrder
from app.services.activity_service import log_activity
from app.services.order_scanner_service import update_order_status
from app.services.task_service import create_task


@register_agent
class OrderFulfillerAgent(BasePolsiaAgent):
    """Fulfills accepted orders by planning and delegating work."""

    agent_type = "order_fulfiller"

    async def run(self, db: AsyncSession, context: dict | None = None) -> dict:
        """Find accepted orders and fulfill them."""
        result = await db.execute(
            select(ExternalOrder)
            .where(ExternalOrder.status == "accepted")
            .order_by(ExternalOrder.created_at.asc())
            .limit(5)
        )
        orders = list(result.scalars().all())
        results = []
        for order in orders:
            result = await self._fulfill(db, order)
            results.append(result)
        return {
            "fulfilled": len(results),
            "results": results,
        }

    async def _fulfill(self, db: AsyncSession, order: ExternalOrder) -> dict:
        await update_order_status(db, order.id, "in_progress")

        fulfill_prompt = json.dumps({
            "order_title": order.title,
            "description": order.description,
            "requirements": order.requirements,
            "platform": order.platform,
            "budget_min": order.budget_min,
            "budget_max": order.budget_max,
            "assigned_agent": order.assigned_agent,
        })

        llm_result = await self.call_llm(
            fulfill_prompt,
            system_prompt=ORDER_FULFILLER_SYSTEM_PROMPT,
        )

        subtasks = llm_result.get("subtasks", [])
        delivery_note = llm_result.get("delivery_note", "Order fulfilled via AI pipeline.")
        tasks_created = 0
        for task_item in subtasks:
            agent = task_item.get("assigned_agent", order.assigned_agent or "code_generation")
            await create_task(
                db,
                title=task_item.get("title", f"Fulfill: {order.title}"),
                agent_type=agent,
                description=task_item.get("description", delivery_note),
                source="order_fulfiller",
            )
            tasks_created += 1

        await update_order_status(
            db, order.id, "completed",
            assigned_agent=order.assigned_agent or "order_fulfiller",
        )

        await log_activity(
            db, agent_type="order_fulfiller", action="order_fulfilled",
            summary=f"Fulfilled order #{order.id}: {order.title} — created {tasks_created} tasks",
        )

        return {
            "order_id": order.id,
            "title": order.title,
            "status": "completed",
            "subtasks_created": tasks_created,
            "delivery_note": delivery_note,
        }
