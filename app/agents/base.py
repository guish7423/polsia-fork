"""Base agent system — call_llm, agent registry, and mock mode."""

import asyncio
import json
import os

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.model_router import (
    TaskCategory,
    agent_category,
    build_request_kwargs,
    fallback_chain,
    select_model,
)

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
    task_category: TaskCategory | None = None
    """Explicit task category for model routing.  ``None`` → inferred from
    :attr:`agent_type` via ``AGENT_CATEGORY`` mapping."""

    async def call_llm(
        self,
        prompt: str,
        system_prompt: str | None = None,
        json_mode: bool = True,
        max_retries: int = 2,
        task_category: TaskCategory | None = None,
    ) -> dict:
        """Call the best available LLM for this agent's task category.

        When ``LLM_API_MOCK=true``, returns a per-agent mock JSON response.

        When a real API call is needed the :mod:`model_router` selects the
        optimal model profile for *task_category* (or the agent's default
        category when omitted).  If the primary profile fails the method
        falls through the remainder of the fallback chain automatically.
        """
        if os.environ.get("LLM_API_MOCK", str(settings.llm_api_mock)).lower() in (
            "true",
            "1",
        ):
            mock = MOCK_RESPONSES.get(self.agent_type, MOCK_RESPONSE)
            return dict(mock)

        import httpx

        category = task_category or self.task_category or agent_category(self.agent_type)
        chain = fallback_chain(category)

        if not chain:
            return {"result": "fallback", "error": "No LLM profiles available", "_fallback": True}

        # Try each profile in priority order
        for profile in chain:
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    kwargs = build_request_kwargs(profile, system_prompt, json_mode)
                    kwargs["json"]["messages"].append(
                        {"role": "user", "content": prompt}
                    )

                    async with httpx.AsyncClient() as client:
                        resp = await client.post(**kwargs)  # type: ignore[arg-type]
                        resp.raise_for_status()
                        data = resp.json()
                        content = data["choices"][0]["message"]["content"]
                        try:
                            return json.loads(content)
                        except json.JSONDecodeError:
                            return {
                                "result": content,
                                "_parse_warning": "LLM returned non-JSON",
                                "_model": profile.name,
                            }
                except (httpx.HTTPError, httpx.TimeoutException, KeyError) as exc:
                    last_error = exc
                    if attempt < max_retries:
                        await asyncio.sleep(2 ** attempt)
                    continue

        # All profiles exhausted
        return {
            "result": "fallback",
            "error": "All models failed",
            "_fallback": True,
        }

    async def run(self, db: AsyncSession, context: dict | None = None) -> dict:
        """Execute the agent's primary logic.

        Subclasses must override this method.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement run()"
        )
