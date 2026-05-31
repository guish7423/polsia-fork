"""Base agent system — call_llm, agent registry, and mock mode."""

import asyncio
import json
import os

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

# Global agent registry
agent_map: dict[str, type["BasePolsiaAgent"]] = {}

MOCK_RESPONSE = {
    "result": "ok",
    "message": "Mock LLM response — agents active in sandbox mode",
    "posts": [],
    "competitors": [],
    "tasks": [],
    "generated_files": [],
    "deployment_tasks": [],
    "suggested_goals": {},
    "suggested_kpis": {},
    "recommendations": [],
    "prospects": [],
    "reply": "Thank you for your message. This is an automated response from our sandbox environment.",
    "requires_escalation": False,
    "status": "healthy",
    "report": "All systems operating normally in sandbox mode.",
    "next_steps": [],
    "morning_plan": "Sandbox mode: continue development and testing.",
    "engagement_insights": "No live data — sandbox environment.",
    "content_themes": [],
    "market_insights": "Sandbox mode — no market data available.",
    "campaign_name": "dev-sandbox-campaign",
    "budget_allocation_usd": 0,
    "optimization_tips": [],
    "recommended_platform": "google_ads",
    "email_subject": "Sandbox test",
    "email_body": "This is a sandbox test message.",
    "revenue_insights": "Sandbox mode — no financial data.",
    "expense_suggestions": [],
    "mrr_cents": 0,
    "arr_cents": 0,
    "active_subscribers": 0,
}

MOCK_RESPONSES: dict[str, dict] = {}


def register_mock(agent_type: str) -> dict:
    """Register or retrieve a mutable mock response dict for an agent type."""
    if agent_type not in MOCK_RESPONSES:
        MOCK_RESPONSES[agent_type] = {**MOCK_RESPONSE}
    return MOCK_RESPONSES[agent_type]


def register_agent(cls):
    """Decorator to register an agent class in agent_map by its agent_type."""
    agent_map[cls.agent_type] = cls
    register_mock(cls.agent_type)
    return cls


class BasePolsiaAgent:
    """Base class for all Polsia agents.

    Subclasses must set ``agent_type`` and implement ``run()``.
    """

    agent_type: str = "base"

    async def call_llm(
        self,
        prompt: str,
        system_prompt: str | None = None,
        json_mode: bool = True,
        max_retries: int = 2,
    ) -> dict:
        """Call LLM API or return mock response.

        When ``LLM_API_MOCK=true``, returns a per-agent mock JSON response.
        Otherwise calls the configured LLM API (DeepSeek-compatible) with
        exponential backoff retry and graceful fallback.
        """
        if os.environ.get("LLM_API_MOCK", str(settings.llm_api_mock)).lower() in (
            "true",
            "1",
        ):
            mock = MOCK_RESPONSES.get(self.agent_type, MOCK_RESPONSE)
            return dict(mock)

        import httpx

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                headers = {
                    "Authorization": f"Bearer {settings.llm_api_key}",
                    "Content-Type": "application/json",
                }
                body = {
                    "model": settings.llm_model,
                    "messages": [],
                    "temperature": 0.7,
                }
                if json_mode:
                    body["response_format"] = {"type": "json_object"}
                if system_prompt:
                    body["messages"].append({"role": "system", "content": system_prompt})
                body["messages"].append({"role": "user", "content": prompt})

                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        f"{settings.llm_api_base_url}/chat/completions",
                        headers=headers,
                        json=body,
                        timeout=120,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    try:
                        return json.loads(content)
                    except json.JSONDecodeError:
                        return {"result": content, "_parse_warning": "LLM returned non-JSON"}
            except (httpx.HTTPError, httpx.TimeoutException, KeyError) as exc:
                last_error = exc
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
                continue

        return {"result": "fallback", "error": str(last_error), "_fallback": True}

    async def run(self, db: AsyncSession, context: dict | None = None) -> dict:
        """Execute the agent's primary logic.

        Subclasses must override this method.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement run()"
        )
