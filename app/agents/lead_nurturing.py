"""Lead Nurturing Agent — auto-follow-up on new sales leads."""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BasePolsiaAgent, register_agent
from app.agents.prompts import LEAD_NURTURING_SYSTEM_PROMPT
from app.models.lead import Lead
from app.models.email import Prospect
from app.services.activity_service import log_activity


@register_agent
class LeadNurturingAgent(BasePolsiaAgent):
    """Nurtures new leads: follows up, qualifies, creates prospects."""

    agent_type = "lead_nurturing"

    async def run(self, db: AsyncSession, context: dict | None = None) -> dict:
        """Find new leads and send follow-up."""
        result = await db.execute(
            select(Lead)
            .where(Lead.status == "new")
            .order_by(Lead.created_at.asc())
            .limit(10)
        )
        leads = list(result.scalars().all())
        results = []
        for lead in leads:
            result = await self._nurture(db, lead)
            results.append(result)
        return {
            "nurtured": len(results),
            "results": results,
        }

    async def _nurture(self, db: AsyncSession, lead: Lead) -> dict:
        nurture_prompt = json.dumps({
            "lead_name": lead.name,
            "email": lead.email,
            "company": lead.company or "Unknown",
            "product_interest": lead.product_interest or "General",
            "budget_range": lead.budget_range or "Not specified",
            "message": lead.message or "",
        })

        llm_result = await self.call_llm(
            nurture_prompt,
            system_prompt=LEAD_NURTURING_SYSTEM_PROMPT,
        )

        email_subject = llm_result.get("email_subject", f"Thanks for your interest, {lead.name}")
        email_body = llm_result.get("email_body", "")
        qualification = llm_result.get("qualification", "unqualified")
        recommended_product = llm_result.get("recommended_product", lead.product_interest or "crossbridge")

        # Create prospect for email outreach
        prospect = Prospect(
            name=lead.name,
            email=lead.email,
            company=lead.company or "",
            status="new",
            source=f"lead_nurturing:{lead.product_interest or 'general'}",
            notes=f"Auto-qualified: {qualification}. Recommended: {recommended_product}. Original inquiry: {lead.message or 'N/A'}",
        )
        db.add(prospect)

        # Update lead status
        lead.status = "contacted"
        await db.flush()

        await log_activity(
            db, agent_type="lead_nurturing", action="lead_followup",
            summary=f"Followed up with {lead.name} ({lead.email}) — {qualification}",
        )

        return {
            "lead_id": lead.id,
            "name": lead.name,
            "email": lead.email,
            "qualification": qualification,
            "recommended_product": recommended_product,
            "email_subject": email_subject,
            "email_body_preview": email_body[:100] + "..." if len(email_body) > 100 else email_body,
        }
