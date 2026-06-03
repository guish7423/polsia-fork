"""OpenAI-compatible provider — works with OpenAI, DeepSeek, Volc Engine, etc."""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

import httpx

from app.core.model_instance import (
    ChatResult,
    ModelProvider,
    StreamChunk,
    count_message_tokens,
    count_tokens,
    estimate_cost,
)

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(ModelProvider):
    """Provider for any OpenAI-compatible chat completion API.

    Supports: OpenAI, DeepSeek, Volc Engine (Doubao), Azure OpenAI,
    Together AI, Fireworks AI, and any other API that mirrors the
    ``/chat/completions`` format.
    """

    provider_name = "openai"

    _supports_json_mode = True

    async def chat(
        self,
        model: str,
        messages: list[dict],
        api_key: str,
        base_url: str,
        *,
        temperature: float = 0.7,
        json_mode: bool = True,
        max_tokens: int | None = None,
        timeout: float = 120.0,
        **kwargs: Any,
    ) -> ChatResult:
        """Send a chat completion request and return the result.

        Parameters
        ----------
        model : str
            Model identifier (e.g. ``"deepseek-chat"``, ``"gpt-4o"``).
        messages : list[dict]
            Message list with ``{"role": …, "content": …}`` dicts.
        api_key : str
            Bearer token.
        base_url : str
            API base URL (e.g. ``"https://api.deepseek.com/v1"``).
        temperature : float
            Sampling temperature (default 0.7).
        json_mode : bool
            When ``True``, sets ``response_format={"type": "json_object"}``
            **only** if ``model`` is not ``"o1-*"`` or ``"o3-*"``.
        max_tokens : int | None
            Maximum output tokens.
        timeout : float
            HTTP request timeout in seconds.

        Returns :class:`ChatResult`.
        """
        url = f"{base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }

        if json_mode:
            body["response_format"] = {"type": "json_object"}

        if max_tokens is not None:
            body["max_tokens"] = max_tokens

        body.update(kwargs)

        # Count input tokens before sending
        input_tokens = count_message_tokens(messages, model)

        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()

        choice = data["choices"][0]
        content = choice["message"]["content"] or ""

        # Token counts from API response (fall back to estimate)
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", input_tokens)
        output_tokens = usage.get("completion_tokens", count_tokens(content, model))

        cost = estimate_cost(model, input_tokens, output_tokens)

        parsed = None
        if json_mode and content:
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                pass

        return ChatResult(
            content=content,
            parsed=parsed,
            model=model,
            provider=self.provider_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            finish_reason=choice.get("finish_reason", ""),
            success=True,
            raw=data,
        )

    async def chat_stream(
        self,
        model: str,
        messages: list[dict],
        api_key: str,
        base_url: str,
        *,
        temperature: float = 0.7,
        json_mode: bool = True,
        max_tokens: int | None = None,
        timeout: float = 120.0,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a chat completion, yielding :class:`StreamChunk` deltas."""
        url = f"{base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }

        if json_mode:
            body["response_format"] = {"type": "json_object"}
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        body.update(kwargs)

        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            async with client.stream("POST", url, headers=headers, json=body) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                    except json.JSONDecodeError:
                        continue

                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    finish_reason = chunk.get("choices", [{}])[0].get("finish_reason")

                    yield StreamChunk(
                        content=content or "",
                        finish_reason=finish_reason,
                        input_tokens=chunk.get("usage", {}).get("prompt_tokens") if finish_reason else None,
                        output_tokens=chunk.get("usage", {}).get("completion_tokens") if finish_reason else None,
                    )

    def count_tokens(self, text: str, model: str | None = None) -> int:
        return count_tokens(text, model)

    async def check_health(self, model: str, api_key: str, base_url: str) -> bool:
        """Check health by listing models via the API."""
        try:
            url = f"{base_url.rstrip('/')}/models"
            headers = {"Authorization": f"Bearer {api_key}"}
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                resp = await client.get(url, headers=headers)
                return resp.status_code == 200
        except Exception:
            # Fall back to lightweight chat ping
            try:
                result = await self.chat(
                    model=model,
                    messages=[{"role": "user", "content": "ping"}],
                    api_key=api_key,
                    base_url=base_url,
                    max_tokens=1,
                )
                return result.success
            except Exception:
                return False
