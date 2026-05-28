"""Base agent system — async call_llm with retry, token tracking, and mock mode."""

import json
import os
import time
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings


# Global agent registry
agent_map: dict[str, type["BasePolsiaAgent"]] = {}


def register_agent(cls):
    """Decorator to register an agent class in agent_map by its agent_type."""
    agent_map[cls.agent_type] = cls
    return cls


@dataclass
class LLMUsage:
    """Tracks LLM API usage for cost monitoring."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    calls: int = 0
    history: list[dict] = field(default_factory=list)

    def record(self, prompt_tokens: int, completion_tokens: int, model: str):
        """Record a usage entry and compute cost."""
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.total_tokens += prompt_tokens + completion_tokens
        self.calls += 1
        # DeepSeek pricing (per 1M tokens)
        # Flash: $0.07 input / $0.28 output
        # Pro: $0.14 input / $0.56 output
        if "flash" in model.lower():
            input_cost = prompt_tokens * 0.07 / 1_000_000
            output_cost = completion_tokens * 0.28 / 1_000_000
        elif "pro" in model.lower():
            input_cost = prompt_tokens * 0.14 / 1_000_000
            output_cost = completion_tokens * 0.56 / 1_000_000
        else:
            input_cost = prompt_tokens * 0.15 / 1_000_000
            output_cost = completion_tokens * 0.60 / 1_000_000
        self.cost_usd += input_cost + output_cost
        self.history.append({
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "input_cost": round(input_cost, 6),
            "output_cost": round(output_cost, 6),
            "total_cost": round(input_cost + output_cost, 6),
            "model": model,
        })

    def summary(self) -> dict:
        return {
            "total_calls": self.calls,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.cost_usd, 4),
            "avg_cost_per_call": round(self.cost_usd / max(self.calls, 1), 6),
        }


# Global usage tracker (per-process)
llm_usage = LLMUsage()


class LLMAPIError(Exception):
    """Raised when the LLM API returns an error after all retries."""
    pass


class BasePolsiaAgent:
    """Base class for all Polsia agents.

    Subclasses must set ``agent_type`` and implement ``run()``.
    """

    agent_type: str = "base"
    max_retries: int = 3
    retry_delay: float = 2.0

    def _is_mock(self) -> bool:
        return os.environ.get("LLM_API_MOCK", str(settings.llm_api_mock)).lower() in (
            "true", "1",
        )

    def _mock_response(self) -> dict:
        raw = os.environ.get("LLM_MOCK_RESPONSE", settings.llm_mock_response)
        return json.loads(raw)

    def _build_messages(
        self, prompt: str, system_prompt: str | None = None
    ) -> list[dict]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    # ── Sync call_llm (for Celery workers, CLI scripts) ──────────────────────

    def call_llm(
        self,
        prompt: str,
        system_prompt: str | None = None,
        json_mode: bool = True,
    ) -> dict:
        """Sync LLM call with retry. Use in Celery workers / sync contexts."""
        if self._is_mock():
            return self._mock_response()

        import httpx

        last_error = None
        for attempt in range(self.max_retries):
            try:
                body = self._build_request_body(prompt, system_prompt, json_mode)
                resp = httpx.post(
                    f"{settings.llm_api_base_url}/chat/completions",
                    headers=self._headers(),
                    json=body,
                    timeout=120,
                )
                resp.raise_for_status()
                data = resp.json()
                return self._parse_response(data, json_mode)
            except (httpx.HTTPError, json.JSONDecodeError, KeyError) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2**attempt))

        raise LLMAPIError(f"LLM call failed after {self.max_retries} retries: {last_error}")

    # ── Async call_llm (for FastAPI async endpoints) ──────────────────────────

    async def call_llm_async(
        self,
        prompt: str,
        system_prompt: str | None = None,
        json_mode: bool = True,
    ) -> dict:
        """Async LLM call with retry. Use in FastAPI / async contexts."""
        if self._is_mock():
            return self._mock_response()

        import httpx

        last_error = None
        for attempt in range(self.max_retries):
            try:
                body = self._build_request_body(prompt, system_prompt, json_mode)
                async with httpx.AsyncClient(timeout=120) as client:
                    resp = await client.post(
                        f"{settings.llm_api_base_url}/chat/completions",
                        headers=self._headers(),
                        json=body,
                    )
                resp.raise_for_status()
                data = resp.json()
                return self._parse_response(data, json_mode)
            except (httpx.HTTPError, json.JSONDecodeError, KeyError) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2**attempt))

        raise LLMAPIError(
            f"LLM call failed after {self.max_retries} retries: {last_error}"
        )

    # ── Shared helpers ────────────────────────────────────────────────────────

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
        }

    def _build_request_body(
        self, prompt: str, system_prompt: str | None = None, json_mode: bool = True
    ) -> dict:
        body: dict = {
            "model": settings.llm_model,
            "messages": self._build_messages(prompt, system_prompt),
            "temperature": 0.7,
            "max_tokens": 4096,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        return body

    def _parse_response(self, data: dict, json_mode: bool) -> dict:
        """Parse LLM response and track usage."""
        choice = data["choices"][0]
        content = choice["message"]["content"]

        # Track token usage
        usage = data.get("usage", {})
        model = data.get("model", settings.llm_model)
        if usage:
            llm_usage.record(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                model=model,
            )

        if json_mode:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {"result": content}
        return {"result": content}

    # ── Agent execution ───────────────────────────────────────────────────────

    async def run(self, db: AsyncSession, context: dict | None = None) -> dict:
        """Execute the agent's primary logic.

        Subclasses must override this method.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement run()"
        )


import asyncio  # noqa: E402 (needed for async sleep in call_llm_async)
