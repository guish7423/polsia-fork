"""Order Scanner Agent — evaluates external orders for fit and profitability."""

import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BasePolsiaAgent, register_agent
from app.agents.prompts import ORDER_SCANNER_SYSTEM_PROMPT
from app.models.external_order import ExternalOrder
from app.services.order_scanner_service import update_order_status


@register_agent
class OrderScannerAgent(BasePolsiaAgent):
    """Scans and evaluates external orders from platforms."""

    agent_type = "order_scanner"

    async def run(self, db: AsyncSession, context: dict | None = None) -> dict:
        """Run scanner: find unscanned orders and evaluate them."""
        from app.services.order_scanner_service import get_orders

        unscanned = await get_orders(db, status="scanned", limit=20)
        results = []
        for order in unscanned:
            result = await self.evaluate(db, order)
            results.append(result)
        return {
            "scanned": len(unscanned),
            "evaluated": len(results),
            "results": results,
        }

    async def evaluate(self, db: AsyncSession, order: ExternalOrder) -> dict:
        evaluate_prompt = json.dumps({
            "order_title": order.title,
            "description": order.description,
            "platform": order.platform,
            "budget_min": order.budget_min,
            "budget_max": order.budget_max,
            "currency": order.currency,
            "requirements": order.requirements,
        })

        llm_result = await self.call_llm(
            evaluate_prompt,
            system_prompt=ORDER_SCANNER_SYSTEM_PROMPT,
        )

        score = llm_result.get("score", 5)
        reason = llm_result.get("reason", "Auto-evaluated")
        assigned = llm_result.get("recommended_agent", "")
        new_status = "accepted" if score >= 6 else "evaluated"

        await update_order_status(
            db,
            order.id,
            new_status,
            score=score,
            score_reason=reason,
            assigned_agent=assigned,
        )

        return {
            "order_id": order.id,
            "title": order.title,
            "score": score,
            "reason": reason,
            "status": new_status,
            "assigned_agent": assigned,
        }
