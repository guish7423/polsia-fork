"""Base agent system — call_llm, agent registry, and mock mode."""

import json
import os

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

# Global agent registry
agent_map: dict[str, type["BasePolsiaAgent"]] = {}


def register_agent(cls):
    """Decorator to register an agent class in agent_map by its agent_type."""
    agent_map[cls.agent_type] = cls
    return cls


class BasePolsiaAgent:
    """Base class for all Polsia agents.

    Subclasses must set ``agent_type`` and implement ``run()``.
    """

    agent_type: str = "base"

    def call_llm(
        self,
        prompt: str,
        system_prompt: str | None = None,
        json_mode: bool = True,
) -> dict:
        """Call LLM API or return mock response.

        When ``LLM_API_MOCK=true``, returns a mock JSON response.
        Otherwise calls the configured LLM API (DeepSeek-compatible).
        """
        if os.environ.get("LLM_API_MOCK", str(settings.llm_api_mock)).lower() in (
            "true",
            "1",
        ):
            return json.loads(os.environ.get("LLM_MOCK_RESPONSE", settings.llm_mock_response))

        import httpx

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

        resp = httpx.post(
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
            return {"result": content}

    async def run(self, db: AsyncSession, context: dict | None = None) -> dict:
        """Execute the agent's primary logic.

        Subclasses must override this method.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement run()"
        )
