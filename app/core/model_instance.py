"""Dify-style ModelInstance — provider abstraction, rate limiting, usage tracking.

Architecture
------------
:class:`ModelProvider`   — abstract base for an API family (OpenAI, Anthropic, …)
:class:`ModelInstance`   — a single configured model (provider + api_key + model name)
:class:`ModelManager`    — global registry that creates and selects instances
:class:`RateLimiter`     — asyncio token-bucket rate limiter
:class:`ModelUsageTracker` — in-memory + optional DB usage recording

Usage
-----
    mgr = ModelManager.get_default()
    inst = mgr.select("content_gen")
    result = await inst.chat([{"role": "user", "content": "Hello"}])
    print(result.content)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, AsyncIterator, Literal

logger = logging.getLogger(__name__)

# ── Typed results ─────────────────────────────────────────────────────────────


@dataclass
class ChatResult:
    """Structured result from a synchronous LLM call."""

    content: str
    """Response text (may be JSON string if json_mode was used)."""
    parsed: dict | list | None = None
    """Parsed JSON when ``json_mode`` was requested, else ``None``."""
    model: str = ""
    provider: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    finish_reason: str = ""
    success: bool = True
    error: str | None = None
    raw: dict | None = None
    """Full response JSON from the provider (for debugging / introspection)."""


@dataclass
class StreamChunk:
    """A single streaming delta."""

    content: str = ""
    """Text delta for this chunk."""
    finish_reason: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


TaskCategory = Literal[
    "content_gen", "analysis", "code", "classification", "summarization", "conversation"
]


# ── Cost tables ───────────────────────────────────────────────────────────────
# (input_cost_per_1k_tokens, output_cost_per_1k_tokens) in USD.

COST_TABLE: dict[str, tuple[float, float]] = {
    # DeepSeek
    "deepseek-chat":           (0.00027, 0.00110),
    "deepseek-reasoner":       (0.00055, 0.00219),
    # GPT-4o family
    "gpt-4o":                  (0.00250, 0.01000),
    "gpt-4o-mini":             (0.00015, 0.00060),
    "gpt-4-turbo":             (0.01000, 0.03000),
    # Claude 3 family
    "claude-3-5-sonnet-20241022": (0.00300, 0.01500),
    "claude-3-haiku-20240307":    (0.00025, 0.00125),
    "claude-3-opus-20240229":     (0.01500, 0.07500),
    # Volc Engine / Doubao
    "doubao-pro-32k":          (0.00080, 0.00080),
    "doubao-lite-32k":         (0.00030, 0.00030),
    # Google Gemini
    "gemini-2.0-flash":        (0.00010, 0.00040),
    "gemini-2.0-pro":          (0.00125, 0.00500),
    # Misc / unknown fallback
    "default":                 (0.00100, 0.00200),
}

CAPABILITY_RANK: dict[str, int] = {
    "content_gen": 1,
    "conversation": 2,
    "summarization": 3,
    "analysis": 4,
    "classification": 5,
    "code": 6,
}


def estimate_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost for *input_tokens* + *output_tokens* on *model_name*."""
    in_cost, out_cost = COST_TABLE.get(model_name, COST_TABLE["default"])
    return (input_tokens / 1000 * in_cost) + (output_tokens / 1000 * out_cost)


# ── Token counting ────────────────────────────────────────────────────────────

_HAVE_TIKTOKEN = False
try:
    import tiktoken as _tiktoken_mod  # type: ignore[import-untyped]
    _HAVE_TIKTOKEN = True
except ImportError:
    pass


_ENCODING_CACHE: dict[str, Any] = {}


def count_tokens(text: str, model: str | None = None) -> int:
    """Count tokens in *text*, preferring tiktoken when available.

    Falls back to ``len(text) // 4`` (rough estimate).
    """
    if not text:
        return 0
    try:
        if _HAVE_TIKTOKEN:
            enc_name = "cl100k_base"
            if model and model not in ("mock",):
                try:
                    encoding = _tiktoken_mod.encoding_for_model(model)  # type: ignore[union-attr]
                    _ENCODING_CACHE[model] = encoding
                except KeyError:
                    encoding = _ENCODING_CACHE.get(model)
                    if encoding is None:
                        encoding = _tiktoken_mod.get_encoding(enc_name)  # type: ignore[union-attr]
                        _ENCODING_CACHE[model] = encoding
            else:
                encoding = _tiktoken_mod.get_encoding(enc_name)  # type: ignore[union-attr]
            return len(encoding.encode(text))
        raise ImportError
    except Exception:
        # Rough char → token approximation
        return len(text) // 4


def count_message_tokens(messages: list[dict], model: str | None = None) -> int:
    """Count tokens for a full message list."""
    total = 0
    for msg in messages:
        total += count_tokens(msg.get("content", "") or "", model)
        total += count_tokens(msg.get("role", ""), model)
        # Approximate overhead per message
        total += 4  # Role overhead
    total += 2  # Assistant prefix
    return total


# ── Rate limiter ──────────────────────────────────────────────────────────────


class RateLimiter:
    """Asyncio token-bucket rate limiter.

    Limits requests per minute (RPM) and tokens per minute (TPM).
    """

    def __init__(self, rpm: int = 60, tpm: int = 100_000):
        self._rpm = rpm
        self._tpm = tpm
        self._tokens_rpm = float(rpm)
        self._tokens_tpm = float(tpm)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, estimated_tokens: int = 0) -> float:
        """Wait until a request slot is available. Returns wait time in seconds."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill

            # Refill RPM tokens
            self._tokens_rpm = min(self._rpm, self._tokens_rpm + elapsed * (self._rpm / 60.0))
            # Refill TPM tokens
            self._tokens_tpm = min(self._tpm, self._tokens_tpm + elapsed * (self._tpm / 60.0))
            self._last_refill = now

            # If either bucket is empty, calculate wait
            wait = 0.0
            if self._tokens_rpm < 1.0:
                wait = max(wait, (1.0 - self._tokens_rpm) / (self._rpm / 60.0))
            if self._tokens_tpm < estimated_tokens:
                wait = max(wait, (estimated_tokens - self._tokens_tpm) / (self._tpm / 60.0))

            if wait > 0:
                await asyncio.sleep(wait)
                # Refill after waiting
                now = time.monotonic()
                elapsed = now - self._last_refill
                self._tokens_rpm = min(self._rpm, self._tokens_rpm + elapsed * (self._rpm / 60.0))
                self._tokens_tpm = min(self._tpm, self._tokens_tpm + elapsed * (self._tpm / 60.0))
                self._last_refill = now

            # Consume tokens
            self._tokens_rpm -= 1.0
            self._tokens_tpm -= max(estimated_tokens, 0)

            return wait


# ── Usage tracker ─────────────────────────────────────────────────────────────


@dataclass
class UsageRecord:
    """In-memory usage record for a single LLM call."""

    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    duration_ms: int
    success: bool
    task_category: str | None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: str | None = None


class ModelUsageTracker:
    """Records LLM usage — in-memory ring buffer with optional DB persistence.

    Usage records are kept in a circular buffer.  When *db_log_enabled* is
    ``True`` and a database session is provided, records are also written to
    the ``model_calls`` table (see ``app.models.model_call.ModelCall``).
    """

    def __init__(self, max_records: int = 1000, db_log_enabled: bool = False):
        self._records: list[UsageRecord] = []
        self._max = max_records
        self._db_log_enabled = db_log_enabled

    @property
    def db_log_enabled(self) -> bool:
        return self._db_log_enabled

    @db_log_enabled.setter
    def db_log_enabled(self, value: bool) -> None:
        self._db_log_enabled = value

    def record(self, record: UsageRecord) -> None:
        """Add an in-memory record. Purges oldest entry if buffer is full."""
        self._records.append(record)
        if len(self._records) > self._max:
            self._records.pop(0)

    async def record_async(self, record: UsageRecord, db_session=None) -> None:
        """Add a record and optionally persist to DB."""
        self.record(record)
        if self._db_log_enabled and db_session is not None:
            await self._persist_to_db(record, db_session)

    async def _persist_to_db(self, record: UsageRecord, db_session) -> None:
        try:
            from app.models.model_call import ModelCall

            mc = ModelCall(
                provider=record.provider,
                model=record.model,
                input_tokens=record.input_tokens,
                output_tokens=record.output_tokens,
                cost_usd=record.cost_usd,
                duration_ms=record.duration_ms,
                success=record.success,
                task_category=record.task_category,
                error=record.error,
            )
            db_session.add(mc)
        except Exception as exc:
            logger.warning("Failed to persist usage record: %s", exc)

    @property
    def total_cost_usd(self) -> float:
        """Sum of all in-memory records."""
        return sum(r.cost_usd for r in self._records)

    @property
    def total_input_tokens(self) -> int:
        return sum(r.input_tokens for r in self._records)

    @property
    def total_output_tokens(self) -> int:
        return sum(r.output_tokens for r in self._records)

    def recent(self, n: int = 10) -> list[UsageRecord]:
        """Return the *n* most recent records."""
        return self._records[-n:]

    def stats_by_model(self) -> dict[str, dict]:
        """Aggregate usage grouped by model name."""
        stats: dict[str, dict] = {}
        for r in self._records:
            key = f"{r.provider}/{r.model}"
            if key not in stats:
                stats[key] = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "errors": 0}
            stats[key]["calls"] += 1
            stats[key]["input_tokens"] += r.input_tokens
            stats[key]["output_tokens"] += r.output_tokens
            stats[key]["cost_usd"] += r.cost_usd
            if not r.success:
                stats[key]["errors"] += 1
        return stats


# ── Model provider (abstract) ─────────────────────────────────────────────────


class ModelProvider(ABC):
    """Abstract base for an LLM API family.

    Subclasses handle the wire format for a single provider (OpenAI-compatible,
    Anthropic, Google, etc.).
    """

    provider_name: str = ""

    @abstractmethod
    async def chat(
        self,
        model: str,
        messages: list[dict],
        api_key: str,
        base_url: str,
        **kwargs: Any,
    ) -> ChatResult:
        """Send a chat completion request and return the full result."""

    async def chat_stream(
        self,
        model: str,
        messages: list[dict],
        api_key: str,
        base_url: str,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a chat completion, yielding StreamChunk deltas.

        Subclasses that support streaming **must** override this with an
        ``async def`` that yields :class:`StreamChunk` values.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support streaming"
        )
        if False:  # pragma: no cover
            yield  # make pyright see this as async generator

    @abstractmethod
    def count_tokens(self, text: str, model: str | None = None) -> int:
        """Count tokens for ``text``.  May use tiktoken or a heuristic."""

    def cost_per_token(self, model: str) -> tuple[float, float]:
        """Return ``(input_cost_per_1k_tokens, output_cost_per_1k_tokens)`` in USD."""
        return COST_TABLE.get(model, COST_TABLE["default"])

    async def check_health(self, model: str, api_key: str, base_url: str) -> bool:
        """Ping the provider to verify it is reachable.  Override for each provider."""
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


# ── Model instance ────────────────────────────────────────────────────────────


@dataclass
class ModelInstance:
    """A fully configured, ready-to-use model.

    Combines a :class:`ModelProvider` with connection details and
    rate-limiting state.
    """

    provider: ModelProvider
    name: str
    model: str
    base_url: str
    api_key: str
    capabilities: set[str] = field(default_factory=set)
    """Task categories this model is optimised for."""
    priority: int = 10
    """Lower = tried first when multiple instances match."""
    requires_key: bool = True
    """When ``True``, ``api_key`` must be non-empty for this instance to be
    considered available."""
    rate_limiter: RateLimiter | None = None
    usage_tracker: ModelUsageTracker | None = None
    max_retries: int = 2

    def __post_init__(self):
        if self.rate_limiter is None:
            self.rate_limiter = RateLimiter()
        if self.usage_tracker is None:
            self.usage_tracker = ModelUsageTracker()

    @property
    def available(self) -> bool:
        """Whether this instance can be used (has API key if required)."""
        if not self.requires_key:
            return True
        return bool(self.api_key)

    async def chat(
        self,
        messages: list[dict],
        *,
        system_prompt: str | None = None,
        json_mode: bool = True,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        db_session=None,
        **kwargs: Any,
    ) -> ChatResult:
        """Call the LLM with rate limiting and usage tracking.

        Parameters
        ----------
        messages : list[dict]
            Chat messages (may or may not include a system message).
        system_prompt : str | None
            Prepended as a system message if provided.
        json_mode : bool
            Request JSON output when the provider supports it.
        temperature : float
            Sampling temperature (default 0.7).
        max_tokens : int | None
            Maximum output tokens.
        db_session : optional
            Async DB session for persisting usage records.

        Returns :class:`ChatResult`.
        """
        if not self.available:
            return ChatResult(
                content="",
                success=False,
                error=f"Model '{self.name}' has no API key",
            )

        msgs = list(messages)
        if system_prompt:
            msgs.insert(0, {"role": "system", "content": system_prompt})

        if json_mode and hasattr(self.provider, "_supports_json_mode") and self.provider._supports_json_mode is False:  # type: ignore[attr-defined]
            json_mode = False  # Provider doesn't support JSON mode

        # Estimate tokens for rate limiter
        estimated_tokens = self.provider.count_tokens(
            " ".join(m.get("content", "") or "" for m in msgs),
            self.model,
        )

        if self.rate_limiter:
            await self.rate_limiter.acquire(estimated_tokens)

        start = time.monotonic()
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                result = await self.provider.chat(
                    model=self.model,
                    messages=msgs,
                    api_key=self.api_key,
                    base_url=self.base_url,
                    temperature=temperature,
                    json_mode=json_mode,
                    max_tokens=max_tokens,
                    **kwargs,
                )

                elapsed_ms = int((time.monotonic() - start) * 1000)
                result.duration_ms = elapsed_ms
                result.provider = self.provider.provider_name
                result.model = self.model

                # Track usage
                if self.usage_tracker:
                    self.usage_tracker.record(
                        UsageRecord(
                            provider=self.provider.provider_name,
                            model=self.model,
                            input_tokens=result.input_tokens,
                            output_tokens=result.output_tokens,
                            cost_usd=result.cost_usd,
                            duration_ms=elapsed_ms,
                            success=True,
                            task_category=None,
                        )
                    )
                    if self.usage_tracker.db_log_enabled and db_session:
                        await self.usage_tracker.record_async(
                            UsageRecord(
                                provider=self.provider.provider_name,
                                model=self.model,
                                input_tokens=result.input_tokens,
                                output_tokens=result.output_tokens,
                                cost_usd=result.cost_usd,
                                duration_ms=elapsed_ms,
                                success=True,
                                task_category=None,
                            ),
                            db_session,
                        )

                return result

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "ModelInstance.chat attempt %d/%d failed: %s",
                    attempt + 1, self.max_retries + 1, exc,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)

        elapsed_ms = int((time.monotonic() - start) * 1000)
        if self.usage_tracker:
            self.usage_tracker.record(
                UsageRecord(
                    provider=self.provider.provider_name,
                    model=self.model,
                    input_tokens=0,
                    output_tokens=0,
                    cost_usd=0.0,
                    duration_ms=elapsed_ms,
                    success=False,
                    task_category=None,
                    error=str(last_error),
                )
            )

        return ChatResult(
            content="",
            success=False,
            error=f"All {self.max_retries + 1} attempts failed: {last_error}",
        )

    async def chat_stream(
        self,
        messages: list[dict],
        *,
        system_prompt: str | None = None,
        json_mode: bool = True,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a chat completion.

        Yields :class:`StreamChunk` deltas.  The last chunk carries
        ``finish_reason`` and token counts.
        """
        if not self.available:
            yield StreamChunk(
                content="",
                finish_reason="error",
            )
            return

        msgs = list(messages)
        if system_prompt:
            msgs.insert(0, {"role": "system", "content": system_prompt})

        estimated_tokens = self.provider.count_tokens(
            " ".join(m.get("content", "") or "" for m in msgs),
            self.model,
        )

        if self.rate_limiter:
            await self.rate_limiter.acquire(estimated_tokens)

        total_input = estimated_tokens
        total_output = 0
        start = time.monotonic()

        try:
            async for chunk in self.provider.chat_stream(
                model=self.model,
                messages=msgs,
                api_key=self.api_key,
                base_url=self.base_url,
                temperature=temperature,
                json_mode=json_mode,
                max_tokens=max_tokens,
                **kwargs,
            ):
                total_output += self.provider.count_tokens(chunk.content, self.model)
                yield chunk

            # Final chunk — track usage
            elapsed_ms = int((time.monotonic() - start) * 1000)
            cost = estimate_cost(self.model, total_input, total_output)

            if self.usage_tracker:
                self.usage_tracker.record(
                    UsageRecord(
                        provider=self.provider.provider_name,
                        model=self.model,
                        input_tokens=total_input,
                        output_tokens=total_output,
                        cost_usd=cost,
                        duration_ms=elapsed_ms,
                        success=True,
                        task_category=None,
                    )
                )

        except Exception as exc:
            logger.error("Streaming failed for %s: %s", self.name, exc)
            yield StreamChunk(content="", finish_reason="error")

    async def check_health(self) -> bool:
        """Check if this model instance is reachable."""
        try:
            return await self.provider.check_health(
                model=self.model,
                api_key=self.api_key,
                base_url=self.base_url,
            )
        except Exception:
            return False


# ── Agent → category mapping ─────────────────────────────────────────────────

AGENT_CATEGORY: dict[str, TaskCategory] = {
    "orchestrator": "analysis",
    "social_media": "content_gen",
    "competitor_research": "analysis",
    "business_planning": "analysis",
    "deployment": "code",
    "finance": "analysis",
    "ads_management": "analysis",
    "email_outreach": "conversation",
    "code_generation": "code",
    "customer_support": "conversation",
    "order_scanner": "classification",
    "order_fulfiller": "analysis",
    "lead_nurturing": "conversation",
    "deploy_agent": "code",
    "monitor": "analysis",
    "evolution": "analysis",
    "market_intel": "summarization",
}


def agent_category(agent_type: str) -> TaskCategory:
    """Return the task category for *agent_type*, defaulting to ``analysis``."""
    return AGENT_CATEGORY.get(agent_type, "analysis")


# ── Model Manager ─────────────────────────────────────────────────────────────


class ModelManager:
    """Global registry of :class:`ModelInstance` and :class:`ModelProvider`.

    Usage
    -----
        manager = ModelManager()
        manager.register_provider(OpenAICompatibleProvider())
        manager.build_default_instances()
        inst = manager.select("content_gen")
    """

    def __init__(self):
        self._providers: dict[str, ModelProvider] = {}
        self._instances: dict[str, ModelInstance] = {}
        self._usage_tracker = ModelUsageTracker()

    # -- provider registry ------------------------------------------------

    def register_provider(self, provider: ModelProvider) -> None:
        """Register a :class:`ModelProvider` by its ``provider_name``."""
        if not provider.provider_name:
            raise ValueError("ModelProvider must have a non-empty provider_name")
        self._providers[provider.provider_name] = provider

    def get_provider(self, name: str) -> ModelProvider | None:
        return self._providers.get(name)

    @property
    def providers(self) -> dict[str, ModelProvider]:
        return dict(self._providers)

    # -- instance management ----------------------------------------------

    def add_instance(self, instance: ModelInstance) -> None:
        """Register a :class:`ModelInstance` by its ``name``."""
        instance.usage_tracker = self._usage_tracker
        self._instances[instance.name] = instance

    def get_instance(self, name: str) -> ModelInstance | None:
        return self._instances.get(name)

    def remove_instance(self, name: str) -> None:
        self._instances.pop(name, None)

    @property
    def instances(self) -> dict[str, ModelInstance]:
        return dict(self._instances)

    @property
    def usage_tracker(self) -> ModelUsageTracker:
        return self._usage_tracker

    # -- selection / routing ----------------------------------------------

    def select(self, task_category: str) -> ModelInstance | None:
        """Return the best available instance for *task_category* (by priority)."""
        sorted_instances = sorted(
            self._instances.values(),
            key=lambda i: i.priority,
        )
        for inst in sorted_instances:
            if task_category not in inst.capabilities:
                continue
            if not inst.available:
                continue
            return inst
        return None

    def fallback_chain(
        self,
        task_category: str,
    ) -> list[ModelInstance]:
        """All available instances matching *task_category*, sorted by priority."""
        sorted_instances = sorted(
            self._instances.values(),
            key=lambda i: i.priority,
        )
        return [
            inst
            for inst in sorted_instances
            if task_category in inst.capabilities and inst.available
        ]

    # -- health checks ----------------------------------------------------

    async def check_health(self, name: str | None = None) -> dict[str, bool]:
        """Check health of all (or one) instances.

        Returns a ``{instance_name: is_healthy}`` dict.
        """
        targets = (
            [self._instances[name]] if name else list(self._instances.values())
        )
        results: dict[str, bool] = {}
        for inst in targets:
            if inst is None:
                continue
            ok = await inst.check_health()
            results[inst.name] = ok
        return results

    # -- default setup ----------------------------------------------------

    def build_from_env(self, env_prefix: str = "LLM_") -> None:
        """Build instances by scanning environment variables.

        Convention::
            LLM_<NAME>_API_KEY  = environment variable name holding the key
            LLM_<NAME>_BASE_URL = base URL (optional, defaults to OpenAI)
            LLM_<NAME>_MODEL    = model name
            LLM_<NAME>_PROVIDER = provider name (default "openai")
        """
        # Built from env — optional.  For now, we rely on the hardcoded
        # build_default_instances() or direct add_instance().

    def build_default_instances(self) -> None:
        """Create the standard set of instances from environment variables.

        Mirrors the ``PROFILES`` list from ``model_router.py``.
        """
        openai_provider = self._providers.get("openai")
        if openai_provider is None:
            logger.warning("OpenAI-compatible provider not registered, skipping defaults")
            return

        instances_config = [
            {
                "name": "DeepSeek V4 Flash",
                "env_api_key": "DEEPSEEK_API_KEY",
                "base_url": "https://api.deepseek.com/v1",
                "model": "deepseek-chat",
                "capabilities": {"analysis", "content_gen", "classification", "summarization", "conversation"},
                "priority": 1,
            },
            {
                "name": "DeepSeek V4 Flash (via LLM_API_KEY)",
                "env_api_key": "LLM_API_KEY",
                "base_url": "os.getenv('LLM_API_BASE_URL', 'https://api.deepseek.com/v1')",
                "model": "os.getenv('LLM_MODEL', 'deepseek-chat')",
                "capabilities": {"analysis", "content_gen", "classification", "summarization", "conversation"},
                "priority": 2,
            },
            {
                "name": "Volc Engine Doubao-pro",
                "env_api_key": "VOLC_ENGINE_API_KEY",
                "base_url": "https://ark.cn-beijing.volces.com/api/v3",
                "model": "doubao-pro-32k",
                "capabilities": {"content_gen", "analysis", "summarization", "conversation"},
                "priority": 3,
            },
            {
                "name": "Volc Engine Doubao-lite",
                "env_api_key": "VOLC_ENGINE_API_KEY",
                "base_url": "https://ark.cn-beijing.volces.com/api/v3",
                "model": "doubao-lite-32k",
                "capabilities": {"classification", "summarization"},
                "priority": 4,
            },
        ]

        for cfg in instances_config:
            resolved_base_url = (
                os.getenv("LLM_API_BASE_URL", "https://api.deepseek.com/v1")
                if cfg["base_url"].startswith("os.")
                else cfg["base_url"]
            )
            resolved_model = (
                os.getenv("LLM_MODEL", "deepseek-chat")
                if cfg["model"].startswith("os.")
                else cfg["model"]
            )
            api_key = os.environ.get(cfg["env_api_key"], os.environ.get("LLM_API_KEY", ""))

            self.add_instance(
                ModelInstance(
                    provider=openai_provider,
                    name=cfg["name"],
                    model=resolved_model,
                    base_url=resolved_base_url,
                    api_key=api_key,
                    capabilities=cfg["capabilities"],
                    priority=cfg["priority"],
                )
            )

    # -- singleton shortcut -------------------------------------------------

    _default: ModelManager | None = None

    @classmethod
    def get_default(cls) -> ModelManager:
        """Return or create the singleton default manager.

        On first call, registers the built-in providers and default instances.
        Also adds a mock fallback instance so there is always at least one
        available model.
        """
        if cls._default is not None:
            return cls._default

        mgr = cls()

        # Lazy imports to avoid circular dependencies
        from app.core.model_providers.openai_compatible import OpenAICompatibleProvider
        from app.core.model_providers.mock import MockProvider

        mgr.register_provider(OpenAICompatibleProvider())
        mgr.register_provider(MockProvider())
        mgr.build_default_instances()

        # Always add a mock fallback
        mock_prov = mgr._providers.get("mock")
        if mock_prov and "Mock" not in mgr._instances:
            mgr.add_instance(
                ModelInstance(
                    provider=mock_prov,
                    name="Mock (fallback)",
                    model="mock",
                    base_url="",
                    api_key="",
                    capabilities={"analysis", "content_gen", "code", "classification", "summarization", "conversation"},
                    priority=99,
                    requires_key=False,
                )
            )

        cls._default = mgr
        return cls._default
