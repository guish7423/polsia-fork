"""Monitor Agent — 守望者, periodic health checks for all CrossWave services."""

import json
import os

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BasePolsiaAgent, register_agent
from app.agents.prompts import MONITOR_SYSTEM_PROMPT
from app.services.monitor_service import (
    check_all_services,
    summarize_results,
)
from app.services.activity_service import log_activity


@register_agent
class MonitorAgent(BasePolsiaAgent):
    """System health monitor — checks all services, logs results, alerts on failure."""

    async def run(self, db: AsyncSession, context: dict | None = None) -> dict:
        # 1. Check all services
        results = await check_all_services(timeout=5)
        summary = summarize_results(results)
        level = "error" if summary["down"] > 0 else "warning" if summary["degraded"] > 0 else "info"

        # 2. Log to activity feed
        down_names = [r["service"] for r in results if r["status"] == "down"]
        degraded_names = [r["service"] for r in results if r["status"] == "degraded"]

        summary_text = (
            f"全部 {summary['total']} 服务: {summary['up']}正常, "
            f"{summary['degraded']}降级, {summary['down']}离线 "
            f"(平均 {summary['avg_response_time_ms']}ms)"
        )
        if down_names:
            summary_text = f"⚠️ 服务离线: {', '.join(down_names)}. " + summary_text

        await log_activity(
            db=db,
            agent_type="monitor",
            action="health_check",
            summary=summary_text,
            level=level,
            detail={
                "results": results,
                "summary": summary,
            },
        )

        # 3. Use LLM to analyze if there are issues
        if summary["down"] > 0 or summary["degraded"] > 0:
            llm_input = json.dumps({"results": results, "summary": summary}, ensure_ascii=False)
            try:
                llm_result = await self.call_llm(llm_input, system_prompt=MONITOR_SYSTEM_PROMPT)
                analysis = json.loads(llm_result) if isinstance(llm_result, str) else llm_result
            except Exception:
                analysis = {"analysis": "LLM analysis unavailable — basic monitoring active."}
        else:
            analysis = {"analysis": "All systems healthy, no action needed."}

        return {
            "summary": summary,
            "results": results,
            "analysis": analysis,
        }
