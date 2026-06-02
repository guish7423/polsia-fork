"""Step-level checkpointing for Celery tasks (Inngest-style durability).

Each checkpoint stores intermediate task results in Redis.  On retry after a
crash, completed steps are *skipped* (their results are restored from Redis).
Only the failed step re-runs.

Usage::

    from app.core.checkpoint import Checkpoint

    async def my_task(task_id: str, ...):
        cp = Checkpoint(task_id, ttl=3600)

        # Step 1 — will be skipped on retry if already done
        data = await cp.run("fetch-data", fetch_data_from_api)

        # Step 2 — will re-run if the original attempt crashed here
        result = await cp.run("process-data", process_data, data)

        # Step 3 — final step
        await cp.run("save", save_to_db, result)
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Redis connection (lazy init — only used when checkpointing is enabled)
_redis = None
REDIS_URL: str | None = None


def _get_redis_url() -> str | None:
    """Lazy resolve Redis URL.  Returns ``None`` if not configured.

    Checked in order:
    1. ``CHECKPOINT_REDIS_URL`` env var (explicit override)
    2. ``CELERY_BROKER_URL`` env var (share Celery's Redis)
    3. ``None`` (checkpointing disabled)
    """
    global REDIS_URL
    if REDIS_URL is None:
        REDIS_URL = (
            os.environ.get("CHECKPOINT_REDIS_URL")
            or os.environ.get("CELERY_BROKER_URL")
        )
    return REDIS_URL


def _get_redis():
    """Lazy-initialise the Redis client.  Returns ``None`` if no Redis URL."""
    global _redis
    if _redis is None:
        url = _get_redis_url()
        if url is None:
            return None
        try:
            import redis.asyncio as aioredis  # type: ignore[import-untyped]
            _redis = aioredis.from_url(url, decode_responses=True)
        except Exception as exc:
            logger.warning("Checkpoint Redis unavailable: %s", exc)
            return None
    return _redis


class Checkpoint:
    """Per-task checkpoint for step-level durability.

    Each step is identified by a ``step_name`` string (e.g. ``"fetch-data"``).
    Results are stored in Redis under the key ``checkpoint:{task_id}:{step_name}``.

    On retry, ``run()`` checks Redis first.  If the step result exists and the
    TTL hasn't expired, the step is skipped and the cached result is returned.
    """

    def __init__(self, task_id: str, ttl: int = 3600) -> None:
        self.task_id = task_id
        self.ttl = ttl
        self._key_prefix = f"checkpoint:{task_id}:"
        self._redis = _get_redis()
        self._fallback_store: dict[str, tuple[float, Any]] = {}
        """In-memory fallback when Redis is unavailable."""

    # ── Public API ────────────────────────────────────────────────────────

    async def run(
        self,
        step_name: str,
        fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute a step, or skip it if a cached result exists.

        If a checkpoint exists for this step:
          - ``fn`` is **not** called
          - the cached result is returned

        Otherwise:
          - ``fn(*args, **kwargs)`` is called
          - the result is checkpointed (stored in Redis)
          - the result is returned

        If Redis is unavailable, falls back to in-memory (process-local)
        storage – still protects against retries within the same process.
        """
        # Try to load cached result (Redis or in‑memory fallback)
        cached = await self._load(step_name)
        if cached is not None:
            logger.debug("Checkpoint HIT  %s/%s", self.task_id, step_name)
            return cached

        # Execute
        logger.debug("Checkpoint MISS %s/%s — executing", self.task_id, step_name)
        result = await self._maybe_await(fn(*args, **kwargs))

        # Store
        await self._save(step_name, result)
        return result

    def checkpoint_key(self, step_name: str) -> str:
        """Full Redis key for a given step."""
        return f"{self._key_prefix}{step_name}"

    # ── Internals ─────────────────────────────────────────────────────────

    def _enabled(self) -> bool:
        """Checkpointing is enabled if Redis URL is configured."""
        return _get_redis_url() is not None

    async def _load(self, step_name: str) -> Any | None:
        """Load a cached step result, or return None."""
        key = self.checkpoint_key(step_name)

        # Try Redis first
        if self._redis is not None:
            try:
                raw = await self._redis.get(key)
                if raw is not None:
                    return json.loads(raw)
            except Exception as exc:
                logger.debug("Checkpoint Redis load failed: %s", exc)

        # Fallback: in-memory store
        entry = self._fallback_store.get(key)
        if entry is not None:
            ts, val = entry
            if time.monotonic() - ts < self.ttl:
                return val
        return None

    async def _save(self, step_name: str, value: Any) -> None:
        """Persist a step result."""
        key = self.checkpoint_key(step_name)
        raw = json.dumps(value, default=str)

        # Redis
        if self._redis is not None:
            try:
                await self._redis.setex(key, self.ttl, raw)
                return
            except Exception as exc:
                logger.debug("Checkpoint Redis save failed: %s", exc)

        # Fallback: in-memory
        self._fallback_store[key] = (time.monotonic(), value)

    async def _maybe_await(self, value: Any) -> Any:
        """Await if the value is a coroutine, else return as-is."""
        if hasattr(value, "__await__"):
            return await value
        return value


# ── Convenience ──────────────────────────────────────────────────────────────

_FACTORY_CACHE: dict[str, Checkpoint] = {}


def get_checkpoint(task_id: str, ttl: int = 3600) -> Checkpoint:
    """Get or create a Checkpoint for a task.  Cached per (task_id)."""
    if task_id not in _FACTORY_CACHE:
        _FACTORY_CACHE[task_id] = Checkpoint(task_id, ttl)
    return _FACTORY_CACHE[task_id]


def clear_checkpoint(task_id: str) -> None:
    """Remove a Checkpoint from the factory cache."""
    _FACTORY_CACHE.pop(task_id, None)
