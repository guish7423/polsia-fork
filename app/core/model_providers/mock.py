"""Mock provider — returns deterministic responses without an API call.

Used when ``LLM_API_MOCK=true`` or when no real API keys are available.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

from app.core.model_instance import (
    ChatResult,
    ModelProvider,
    StreamChunk,
    count_tokens,
)


MOCK_CHAT_RESPONSE = {
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
    "reply": "Thank you for your message.",
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


class MockProvider(ModelProvider):
    """In-process mock that returns canned responses without network calls.

    Useful for testing, development, and sandbox mode.  The response can be
    customised by passing ``mock_response`` to :meth:`chat`.
    """

    provider_name = "mock"

    def __init__(self, mock_response: dict | None = None):
        self.mock_response = mock_response or MOCK_CHAT_RESPONSE

    async def chat(
        self,
        model: str,
        messages: list[dict],
        api_key: str = "",
        base_url: str = "",
        **kwargs: Any,
    ) -> ChatResult:
        """Return the canned mock response immediately.

        ``kwargs.get("mock_response")`` overrides the default mock response
        for this call.
        """
        import time

        response = kwargs.get("mock_response", self.mock_response)
        content = json.dumps(response, ensure_ascii=False)

        json_mode = kwargs.get("json_mode", True)
        parsed = None
        if json_mode:
            parsed = response

        # Simulate a tiny latency
        await asyncio.sleep(0.05)

        text_length = sum(len(str(v)) for v in response.values()) if isinstance(response, dict) else len(content)

        return ChatResult(
            content=content,
            parsed=parsed,
            model=model,
            provider=self.provider_name,
            input_tokens=count_tokens("mock input", model),
            output_tokens=count_tokens(content, model),
            cost_usd=0.0,
            duration_ms=50,
            finish_reason="stop",
            success=True,
            raw={"mock": True, "response": response},
        )

    async def chat_stream(
        self,
        model: str,
        messages: list[dict],
        api_key: str = "",
        base_url: str = "",
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        """Yield the mock response as a single stream chunk."""
        import time

        response = kwargs.get("mock_response", self.mock_response)
        content = json.dumps(response, ensure_ascii=False)

        await asyncio.sleep(0.05)
        yield StreamChunk(content=content)
        yield StreamChunk(
            finish_reason="stop",
            input_tokens=count_tokens("mock input", model),
            output_tokens=count_tokens(content, model),
        )

    def count_tokens(self, text: str, model: str | None = None) -> int:
        return len(text) // 4

    async def check_health(self, model: str, api_key: str, base_url: str) -> bool:
        """Mock is always healthy."""
        return True
