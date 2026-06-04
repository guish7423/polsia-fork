"""Base agent system — call_llm, agent registry, sandbox, and mock mode."""

import asyncio
import json
import os
from typing import Any, AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.model_instance import StreamChunk
from app.services.model_router import (
    TaskCategory,
    agent_category,
    build_request_kwargs,
    fallback_chain,
    fallback_instances,
    select_model,
)
from app.services.sandbox_service import (
    SANDBOX_ENABLED,
    check_action,
    submit_pending_action,
)

# Global agent registry
agent_map: dict[str, type["BasePolsiaAgent"]] = {}

# ─── Sandbox Helpers ─────────────────────────────────────────────────────────
# Agent-type-based sandbox rules checked at trigger time.
# Two levels: "approval" (queue for HQ review) and "block" (reject outright).

_AGENT_SANDBOX_RULES: dict[str, str] = {
    # agent_type → rule_id (only high-risk agents in production)
    "finance": "finance_change",
}


def sandbox_verdict(agent_type: str, action_type: str = "trigger_agent") -> dict[str, Any]:
    """Evaluate an agent‐level action against the sandbox.

    Returns one of:
      ``{"verdict": "allow"}``
      ``{"verdict": "block", "rule_id": …, "message": …}``
      ``{"verdict": "pending", "rule_id": …, "message": …}``
    """
    rule_id = _AGENT_SANDBOX_RULES.get(agent_type)
    if rule_id is None:
        return {"verdict": "allow", "rule_id": None, "message": "No matching rule"}

    result = check_action(action_type=action_type, agent_type=agent_type)
    if result["verdict"] in ("block", "pending"):
        return result

    return {"verdict": "allow", "rule_id": None, "message": "Action allowed"}


def submit_sandbox_action(
    agent_type: str,
    action_type: str = "trigger_agent",
    summary: str | None = None,
    metadata: dict | None = None,
) -> dict[str, Any]:
    """Submit an agent trigger for human approval and return the pending record."""
    return submit_pending_action(
        action_type=action_type,
        agent_type=agent_type,
        summary=summary or f"{agent_type} agent execution requested",
        payload=metadata or {},
        rule_id=_AGENT_SANDBOX_RULES.get(agent_type),
    )


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

    _function_calling_enabled: bool = False
    """Set by ``run_agent()`` when ``function_calling=True``.  Agent
    subclasses can check this flag in their ``run()`` method and choose
    ``call_llm_with_tools()`` over ``call_llm()`` accordingly."""

    _gen_config_overrides: dict | None = None
    """Cached generation config overrides, populated lazily by
    :meth:`_load_gen_config_overrides` and read by :meth:`_get_gen_config_overrides`."""

    def _get_gen_config_overrides(self) -> dict:
        """Return cached generation config overrides — or ``{}`` when disabled.

        The cache is populated lazily by :meth:`call_llm` (which has access
        to a ``db_session``).  Config changes are rare and agents restart
        periodically, so no TTL invalidation is needed.
        """
        if not settings.config_tuner_enabled:
            return {}
        if self._gen_config_overrides is not None:
            return self._gen_config_overrides
        return {}

    async def _load_gen_config_overrides(
        self, db_session: AsyncSession,
    ) -> dict:
        """Fetch and cache overrides from :class:`ConfigTunerService`.

        Fail-open: returns ``{}`` on any error so the agent never blocks.
        """
        if not settings.config_tuner_enabled:
            self._gen_config_overrides = {}
            return {}
        try:
            from app.services.config_tuner import ConfigTunerService

            config = await ConfigTunerService.get_effective_config(
                db_session, tenant_id=1, agent_type=self.agent_type,
            )
            self._gen_config_overrides = config
            return config
        except Exception:
            self._gen_config_overrides = {}
            return {}

    # ── RAG Context Injection ─────────────────────────────────────────────

    async def _build_rag_context(
        self,
        tenant_id: int,
        query: str,
        db_session: AsyncSession | None = None,
    ) -> str:
        """Build a RAG context block from semantic memory search results.

        Queries the knowledge base via ``semantic_search_memory()`` and
        formats matching entries as a markdown ``<knowledge_context>`` block
        that gets prepended to the LLM prompt.

        Fail-open: returns ``""`` on any exception so agent execution is
        never blocked by a RAG service failure.

        Args:
            tenant_id: Scopes the search to a specific tenant.
            query: The prompt text used as the similarity search query.
            db_session: Optional DB session.  When ``None`` the method
                lazy-imports a session from the global engine.

        Returns:
            A markdown-formatted context string, or ``""`` when no results
            are available or on any error.
        """
        _session: AsyncSession | None = db_session
        _owns_session = False
        if _session is None:
            try:
                from app.core.database import async_session as _async_session_factory

                _session = _async_session_factory()
                _owns_session = True
            except Exception:
                return ""
        try:
            from app.services.memory_service import semantic_search_memory

            results = await semantic_search_memory(
                _session,
                query=query,
                tenant_id=tenant_id,
                n_results=5,
            )
            if not results:
                return ""

            lines = ["<knowledge_context>"]
            for i, entry in enumerate(results, 1):
                source = entry.source or "unknown"
                lines.append(f"  [{i}] ({source}) {entry.title}")
                lines.append(f"      {entry.content}")
            lines.append("</knowledge_context>")
            return "\n".join(lines)
        except Exception:
            return ""
        finally:
            if _owns_session and _session is not None:
                await _session.close()

    # ── Agent Step Streaming (SSE) ────────────────────────────────────────

    def publish_step(self, step_type: str, content: str, timestamp: str | None = None) -> None:
        """Publish a streaming step event for this agent (non-blocking, fail-open).

        Args:
            step_type: Short label — ``"thinking"``, ``"tool_call"``,
                ``"llm_start"``, ``"llm_end"``, etc.
            content: Human-readable description.
            timestamp: ISO-8601 string; ``None`` → current time.
        """
        if not settings.agent_streaming_enabled:
            return
        try:
            from app.core.agent_stream import AgentStreamManager
            AgentStreamManager.get_instance().publish_step(
                self.agent_type, step_type, content, timestamp,
            )
        except Exception:
            pass  # Streaming must never break agent execution

    async def call_llm(
        self,
        prompt: str,
        system_prompt: str | None = None,
        json_mode: bool = True,
        max_retries: int = 2,
        task_category: TaskCategory | None = None,
        db_session=None,
        tenant_id: int | None = None,
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
            self.publish_step("llm_end", "Mock LLM response returned")
            return dict(mock)

        import httpx

        from app.config import settings as app_settings
        from app.services.model_usage_service import record_model_call

        category = task_category or self.task_category or agent_category(self.agent_type)
        chain = fallback_chain(category)

        if not chain:
            return {"result": "fallback", "error": "No LLM profiles available", "_fallback": True}

        last_error: Exception | None = None

        # Try each profile in priority order
        for profile in chain:
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    kwargs = build_request_kwargs(profile, system_prompt, json_mode)
                    kwargs["json"]["messages"].append(
                        {"role": "user", "content": prompt}
                    )

                    # ▼ merge gen_config overrides from ConfigTunerService
                    if db_session is not None:
                        overrides = await self._load_gen_config_overrides(db_session)
                        if overrides:
                            kwargs["json"]["temperature"] = overrides.get(
                                "temperature",
                                kwargs["json"].get("temperature", 0.7),
                            )
                            if "max_tokens" in overrides:
                                kwargs["json"]["max_tokens"] = overrides["max_tokens"]
                            if "top_p" in overrides:
                                kwargs["json"]["top_p"] = overrides["top_p"]

                    # ▼ inject RAG context from knowledge base
                    if tenant_id is not None and settings.rag_enabled:
                        rag_ctx = await self._build_rag_context(tenant_id, prompt, db_session)
                        if rag_ctx:
                            existing = kwargs["json"]["messages"][-1]["content"]
                            kwargs["json"]["messages"][-1]["content"] = existing + "\n\n" + rag_ctx

                    self.publish_step("llm_start", f"Calling {profile.model}...")
                    import time as _time
                    _start = _time.monotonic()
                    async with httpx.AsyncClient() as client:
                        resp = await client.post(**kwargs)  # type: ignore[arg-type]
                        resp.raise_for_status()
                        data = resp.json()
                    _elapsed_ms = int((_time.monotonic() - _start) * 1000)
                    self.publish_step("llm_end", f"LLM responded in {_elapsed_ms}ms")

                    content = data["choices"][0]["message"]["content"]

                    # Estimate token usage from response
                    usage = data.get("usage", {})
                    _in = usage.get("prompt_tokens", len(prompt) // 4)
                    _out = usage.get("completion_tokens", len(content) // 4)

                    # Log usage when db_session is available and tracking is enabled
                    if app_settings.model_usage_log_enabled and db_session is not None:
                        from app.core.model_instance import estimate_cost
                        _cost = estimate_cost(profile.model, _in, _out)
                        try:
                            await record_model_call(
                                db_session,
                                provider="openai",
                                model=profile.model,
                                input_tokens=_in,
                                output_tokens=_out,
                                cost_usd=_cost,
                                duration_ms=_elapsed_ms,
                                success=True,
                                task_category=category,
                            )
                        except Exception:
                            pass  # Usage logging should never break agent execution

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

        # All profiles exhausted — log failure when applicable
        if app_settings.model_usage_log_enabled and db_session is not None:
            try:
                await record_model_call(
                    db_session,
                    provider="unknown",
                    model="",
                    input_tokens=0,
                    output_tokens=0,
                    cost_usd=0.0,
                    duration_ms=0,
                    success=False,
                    task_category=category,
                    error=str(last_error) if last_error else "all profiles exhausted",
                )
            except Exception:
                pass

        return {
            "result": "fallback",
            "error": "All models failed",
            "_fallback": True,
        }

    async def call_llm_with_tools(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tool_rounds: int = 5,
        task_category: TaskCategory | None = None,
        db_session=None,
        tenant_id: int | None = None,
    ) -> dict:
        """Multi-round LLM call with tool execution via :class:`ModelInstance.chat()`.

        Delegates to :func:`app.agents.tool_agent.call_llm_with_tools`.

        Args:
            prompt: The user query / instruction.
            system_prompt: Optional system-level instruction.
            max_tool_rounds: Maximum tool-calling rounds (default 5).
            task_category: Override the agent's default task category.
            db_session: Database session for tool lookups.
            tenant_id: Tenant scope.  ``None`` → no tools loaded.

        Returns:
            Dict with ``"result"`` key, or parsed JSON on the final round.
        """
        from app.agents.tool_agent import call_llm_with_tools as _call

        return await _call(
            agent_type=self.agent_type,
            task_category=self.task_category,
            prompt=prompt,
            system_prompt=system_prompt,
            max_tool_rounds=max_tool_rounds,
            task_category_override=task_category,
            db_session=db_session,
            tenant_id=tenant_id,
        )

    async def call_llm_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        json_mode: bool = False,
        task_category: TaskCategory | None = None,
        tenant_id: int | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a response from the best available LLM for this agent.

        Yields :class:`StreamChunk` deltas.  Uses the new
        :class:`ModelInstance` abstraction internally.

        When ``LLM_API_MOCK=true``, yields the full mock response as a
        single chunk then a finish chunk.

        Usage::

            async for chunk in agent.call_llm_stream("Hello"):
                print(chunk.content, end="")
        """
        if os.environ.get("LLM_API_MOCK", str(settings.llm_api_mock)).lower() in (
            "true",
            "1",
        ):
            mock = MOCK_RESPONSES.get(self.agent_type, MOCK_RESPONSE)
            yield StreamChunk(content=json.dumps(mock, ensure_ascii=False))
            yield StreamChunk(finish_reason="stop")
            return

        category = task_category or self.task_category or agent_category(self.agent_type)
        instances = fallback_instances(category)

        if not instances:
            yield StreamChunk(content="", finish_reason="error")
            return

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # ▼ inject RAG context from knowledge base
        if tenant_id is not None and settings.rag_enabled:
            rag_ctx = await self._build_rag_context(tenant_id, prompt, None)
            if rag_ctx:
                messages[-1]["content"] = prompt + "\n\n" + rag_ctx

        # ▼ read cached gen_config overrides (populated by call_llm when db_session was available)
        _stream_overrides = self._get_gen_config_overrides()
        _stream_temperature = _stream_overrides.get("temperature", 0.7)
        _stream_max_tokens = _stream_overrides.get("max_tokens")

        for instance in instances:
            try:
                async for chunk in instance.chat_stream(
                    messages=messages,
                    json_mode=json_mode,
                    temperature=_stream_temperature,
                    max_tokens=_stream_max_tokens,
                ):
                    yield chunk
                # Streaming succeeded — don't fall through
                return
            except NotImplementedError:
                # Provider doesn't support streaming; fall through
                continue
            except Exception as exc:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    "Streaming failed for %s, trying next instance: %s",
                    instance.name, exc,
                )
                continue

        # All instances exhausted
        yield StreamChunk(content="", finish_reason="error")

    async def run(self, db: AsyncSession, context: dict | None = None) -> dict:
        """Execute the agent's primary logic.

        Subclasses must override this method.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement run()"
        )

    def request_interrupt(
        self,
        reason: str,
        agent_result: dict | None = None,
    ) -> dict:
        """Create a HITL interrupt point during agent execution.

        When an agent encounters a decision that needs human judgment, it
        calls this method to create an interrupt in the pending queue.
        The agent should return the resulting dict from ``run()`` so the
        Celery task pauses and waits for HQ approval.

        Usage inside an agent's ``run()``::

            if budget > 1000:
                return self.request_interrupt(
                    reason=f"Budget ${budget} exceeds ${1000} threshold",
                    agent_result={"budget": budget, "proposal": ...},
                )
        """
        from app.core.interrupt_service import create_interrupt

        iid = create_interrupt(
            agent_type=self.agent_type,
            task_id=0,
            reason=reason,
            context={
                "agent_type": self.agent_type,
                "reason": reason,
                "agent_result": agent_result or {},
            },
        )
        return {
            "status": "interrupt",
            "interrupt_id": iid,
            "reason": reason,
            "message": "Awaiting human approval via HQ — interrupt #{iid}",
        }

    # ── Agent Mesh Methods ─────────────────────────────────────────────────

    async def send_message(
        self,
        db: AsyncSession,
        message_type: str,
        title: str,
        *,
        recipient_type: str | None = None,
        body: dict | None = None,
        priority: int = 3,
    ) -> dict:
        """Send a message through the agent mesh.

        Args:
            db: Database session.
            message_type: 'generic', 'delegation', 'broadcast', 'result'.
            title: Short message title.
            recipient_type: Target agent type. None = broadcast.
            body: JSON payload.
            priority: 1-5 priority.

        Returns:
            Dict with message_id and status.
        """
        from app.services.mesh_bus import send_message as _send

        msg = await _send(
            db=db,
            # TODO: resolve from self.tenant_id or tenant context (Phase C adds proper resolution)
            tenant_id=1,
            sender_type=self.agent_type,
            recipient_type=recipient_type,
            message_type=message_type,
            title=title,
            body=body,
            priority=priority,
        )
        return {"message_id": msg.id, "status": "sent"}

    async def receive_messages(
        self,
        db: AsyncSession,
        status: str | None = "pending",
        limit: int = 10,
    ) -> list[dict]:
        """Fetch incoming mesh messages for this agent.

        Args:
            db: Database session.
            status: Filter by status ('pending', 'delivered', 'read', None=all).
            limit: Max messages to return.

        Returns:
            List of message dicts.
        """
        from app.services.mesh_bus import get_messages_for_agent

        msgs = await get_messages_for_agent(
            db=db,
            tenant_id=1,  # TODO: resolve from self.tenant_id in Phase C
            agent_type=self.agent_type,
            status=status,
            limit=limit,
        )
        return [
            {
                "id": m.id,
                "sender_type": m.sender_type,
                "message_type": m.message_type,
                "title": m.title,
                "body": m.body,
                "priority": m.priority,
                "status": m.status,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in msgs
        ]

    def query_capabilities(
        self,
        capability: str,
        min_tier: str | None = None,
    ) -> list[dict]:
        """Find other agents that have a specific capability.

        Args:
            capability: The capability to search (e.g. 'web_search').
            min_tier: Optional minimum tier filter.

        Returns:
            List of matching agent descriptors.
        """
        from app.services.capability_registry import find_agents_by_capability

        return find_agents_by_capability(capability, min_tier=min_tier)

    async def delegate_to_agent(
        self,
        db: AsyncSession,
        capability: str,
        title: str,
        *,
        body: dict | None = None,
        min_tier: str | None = None,
        priority: int = 3,
    ) -> dict:
        """Delegate a subtask to the best agent that has a specific capability.

        Routes the message using the capability registry, falling back to
        direct agent_type routing if needed. Returns the message status and
        the target agent type.

        Args:
            db: Database session.
            capability: Required capability (e.g. 'web_search').
            title: Short task description.
            body: Task payload.
            min_tier: Minimum tier for the target agent.
            priority: 1-5 priority.

        Returns:
            Dict with message_id, target_agent, status.
            If no agent found, returns {"status": "no_agent_found"}.
        """
        from app.services.mesh_bus import send_to_capability

        msg = await send_to_capability(
            db=db,
            tenant_id=1,  # TODO: resolve from self.tenant_id in Phase C
            sender_type=self.agent_type,
            capability=capability,
            title=title,
            body=body,
            min_tier=min_tier,
            priority=priority,
        )
        if msg is None:
            return {"status": "no_agent_found", "capability": capability}
        return {
            "message_id": msg.id,
            "target_agent": msg.recipient_type,
            "status": "delegated",
        }
