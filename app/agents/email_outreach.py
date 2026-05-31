"""EmailOutreach Agent — prospect management and email campaigns."""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BasePolsiaAgent, register_agent
from app.agents.prompts import EMAIL_OUTREACH_SYSTEM_PROMPT
from app.models.email import EmailCampaign, EmailLog, Prospect
from app.services.activity_service import log_activity


@register_agent
class EmailOutreachAgent(BasePolsiaAgent):
    """Manages prospects, campaigns, and email sequences."""

    agent_type = "email_outreach"

    async def run(self, db: AsyncSession, context: dict | None = None) -> dict:
        prompt = json.dumps({
            "task": "Generate prospect ideas and email outreach content",
        })

        llm_result = await self.call_llm(prompt, system_prompt=EMAIL_OUTREACH_SYSTEM_PROMPT)

        # Create prospect records
        prospects_data = llm_result.get("prospects", [])
        prospects_created = 0
        for p_data in prospects_data:
            existing = await db.execute(
                select(Prospect).where(Prospect.email == p_data.get("email", ""))
            )
            if not existing.scalar_one_or_none():
                prospect = Prospect(
                    email=p_data.get("email", ""),
                    first_name=p_data.get("first_name"),
                    company=p_data.get("company"),
                    source="ai_generated",
                    status="new",
                )
                db.add(prospect)
                prospects_created += 1

        # Create email campaign
        campaign_name = llm_result.get("campaign_name", f"Campaign {id(self)}")
        campaign = EmailCampaign(
            name=campaign_name,
            goal="Initial outreach",
            status="active",
        )
        db.add(campaign)
        await db.flush()  # Ensure prospects + campaign have IDs

        # Create email log entries for new prospects
        subject = llm_result.get("email_subject", "Hello")
        body = llm_result.get("email_body", "Introduction message")
        email_logs_count = 0
        for p_data in prospects_data[:5]:
            # Look up prospect by email to get its ID
            match = await db.execute(
                select(Prospect).where(Prospect.email == p_data.get("email", ""))
            )
            prospect = match.scalar_one_or_none()
            if not prospect:
                continue
            email = EmailLog(
                prospect_id=prospect.id,
                campaign_id=campaign.id,
                sequence_step=1,
                subject=subject,
                body=body,
                status="draft",
            )
            db.add(email)
            email_logs_count += 1

        await db.flush()

        await log_activity(
            db, agent_type="email_outreach", action="campaign_created",
            summary=f"Campaign '{campaign_name}' with {email_logs_count} emails",
        )

        return {
            "result": "email_outreach_complete",
            "campaign": campaign_name,
            "prospects_added": prospects_created,
            "emails_prepared": email_logs_count,
        }
