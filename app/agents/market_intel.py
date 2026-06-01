"""Market Intelligence Agent (市场情报采集组) — scans web for industry news, competitor intel, and opportunities."""

import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BasePolsiaAgent, register_agent
from app.agents.prompts import MARKET_INTEL_SYSTEM_PROMPT
from app.services.intel_service import gather_intel, save_briefing
from app.services.activity_service import log_activity


@register_agent
class MarketIntelAgent(BasePolsiaAgent):
    """Market Intelligence Agent — collects industry news, competitor intel,
    and opportunity signals from web sources. Generates daily briefing."""

    agent_type = "market_intel"

    async def run(self, db: AsyncSession, context: dict | None = None) -> dict:
        """Run intelligence gathering cycle."""
        intel = await gather_intel()
        summary = await self._generate_summary(intel)

        briefing = {
            "type": "market_intel_briefing",
            "timestamp": intel["collected_at"],
            "total_results": intel["total_results"],
            "summary": summary,
            "top_results": intel["results"][:10],
        }
        save_briefing(briefing)

        await log_activity(
            db=db,
            agent_type="market_intel",
            action="briefing_generated",
            summary=f"Daily briefing collected — {intel['total_results']} results from {intel['total_sources']} queries",
            level="info",
            detail={"total_results": intel["total_results"], "total_sources": intel["total_sources"]},
        )

        return {
            "status": "completed",
            "total_results": intel["total_results"],
            "total_sources": intel["total_sources"],
            "summary": summary,
        }

    async def _generate_summary(self, intel: dict) -> str:
        """Use LLM to generate structured summary from raw intel."""
        if not intel["results"]:
            return "No intelligence collected in this cycle."

        prompt = self._build_prompt(intel)
        try:
            llm_result = await self.call_llm(prompt=prompt, system_prompt=MARKET_INTEL_SYSTEM_PROMPT)
            if isinstance(llm_result, dict):
                return json.dumps(llm_result, ensure_ascii=False)
            return str(llm_result)
        except Exception:
            lines = [f"- {r['title']}" for r in intel["results"][:10]]
            return "Key findings:\n" + "\n".join(lines)

    def _build_prompt(self, intel: dict) -> str:
        """Build LLM prompt from raw intel data."""
        items = "\n".join(
            f"- {r.get('title', '')}: {r.get('snippet', '')[:200]}"
            for r in intel["results"][:15]
        )
        return f"""Analyze the following market intelligence results and produce:

1. **Key Trends** (2-3 most important trends relevant to CrossWave's business — AI SaaS, content marketing, deployment services)
2. **Competitor Moves** (any notable competitor activity)
3. **Opportunities** (specific business opportunities or angles)
4. **Action Items** (what CrossWave should do based on this intelligence)

Raw data:
{items}

Total sources queried: {intel['total_sources']}
Total unique results: {intel['total_results']}"""
