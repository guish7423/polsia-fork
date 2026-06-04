"""Agent self-optimization service.

Analyzes agent performance metrics and generates optimization recommendations.
Optimizations are logged but NOT auto-applied — that requires Phase D's
A/B test framework.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.agent_run import AgentRun
from app.models.optimization_log import OptimizationLog

COOLDOWN_HOURS: int = 24
"""Minimum hours between optimizations per (tenant_id, agent_type)."""


class SelfOptimizerService:
    """Feedback-driven agent self-optimization.

    All methods are ``@staticmethod`` so they can be called without
    instantiation.
    """

    @staticmethod
    async def analyze_agent_performance(
        db: AsyncSession,
        tenant_id: int,
        agent_type: str,
    ) -> dict:
        """Analyze the last 50 AgentRun records for the given agent_type.

        Returns:
            dict with keys: success_rate, avg_duration_ms, avg_tokens_per_run,
            token_efficiency, total_runs.
        """
        # Fetch last 50 runs for this agent_type and tenant
        stmt = (
            select(AgentRun)
            .where(
                AgentRun.tenant_id == tenant_id,
                AgentRun.agent_type == agent_type,
            )
            .order_by(AgentRun.started_at.desc())
            .limit(50)
        )
        rows = (await db.execute(stmt)).scalars().all()

        total = len(rows)
        if total == 0:
            return {
                "success_rate": 0.0,
                "avg_duration_ms": 0.0,
                "avg_tokens_per_run": 0,
                "token_efficiency": 0.0,
                "total_runs": 0,
            }

        completed = sum(1 for r in rows if r.status == "completed")
        failed = sum(1 for r in rows if r.status == "failed")

        success_rate = completed / total if total > 0 else 0.0

        durations = [r.duration_secs for r in rows if r.duration_secs is not None]
        avg_duration_ms = (sum(durations) / len(durations) * 1000) if durations else 0.0

        tokens = [r.tokens_used for r in rows if r.tokens_used is not None]
        avg_tokens_per_run = int(sum(tokens) / len(tokens)) if tokens else 0

        # Token efficiency: tokens used in successful runs / total tokens
        successful_tokens = sum(
            r.tokens_used or 0 for r in rows if r.status == "completed"
        )
        total_tokens = sum(r.tokens_used or 0 for r in rows)
        token_efficiency = (
            successful_tokens / total_tokens if total_tokens > 0 else 0.0
        )

        return {
            "success_rate": round(success_rate, 4),
            "avg_duration_ms": round(avg_duration_ms, 2),
            "avg_tokens_per_run": avg_tokens_per_run,
            "token_efficiency": round(token_efficiency, 4),
            "total_runs": total,
        }

    @staticmethod
    async def _get_latest_optimization(
        db: AsyncSession,
        tenant_id: int,
        agent_type: str,
    ) -> OptimizationLog | None:
        """Return the most recent optimization log for the given scope."""
        stmt = (
            select(OptimizationLog)
            .where(
                OptimizationLog.tenant_id == tenant_id,
                OptimizationLog.agent_type == agent_type,
            )
            .order_by(OptimizationLog.created_at.desc())
            .limit(1)
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def optimize_agent(
        db: AsyncSession,
        tenant_id: int,
        agent_type: str,
    ) -> OptimizationLog | None:
        """Run optimization for a single agent type.

        1. If ``self_optimization_enabled`` is False → return ``None``.
        2. If optimized within the last ``COOLDOWN_HOURS`` → return existing log.
        3. Analyze performance → log recommendation → persist.

        Returns:
            The newly created (or recent existing) OptimizationLog, or
            ``None`` when disabled.
        """
        if not settings.self_optimization_enabled:
            return None

        # Cooldown check: skip if optimized within COOLDOWN_HOURS
        latest = await SelfOptimizerService._get_latest_optimization(
            db, tenant_id, agent_type,
        )
        if latest is not None:
            age = datetime.now(timezone.utc) - latest.created_at.replace(tzinfo=timezone.utc)
            if age < timedelta(hours=COOLDOWN_HOURS):
                return latest  # Return existing log (cooldown active)

        # Analyze current performance
        metrics = await SelfOptimizerService.analyze_agent_performance(
            db, tenant_id, agent_type,
        )

        # Compare to baseline (last optimization's after_value, if any)
        baseline_value = latest.after_value if latest else None
        if baseline_value is None:
            # First optimization — use current metrics as baseline
            baseline_value = 1.0 if metrics["total_runs"] > 0 else 0.0

        # Determine which metric needs attention
        if metrics["total_runs"] == 0:
            # No data — nothing to optimize
            return None

        # Find the most actionable metric
        if metrics["success_rate"] < 0.7:
            metric = "success_rate"
            before_value = metrics["success_rate"]
            after_value = baseline_value
            adjustment = {
                "suggestion": "prompt_tuning",
                "detail": (
                    f"Success rate {metrics['success_rate']:.1%} is below 70%. "
                    "Consider prompt refinement or model configuration changes."
                ),
                "requires_phase_d": True,
            }
        elif metrics["avg_tokens_per_run"] > baseline_value * 1.2 and baseline_value > 0:
            metric = "avg_duration"
            before_value = metrics["avg_duration_ms"]
            after_value = baseline_value
            adjustment = {
                "suggestion": "generation_config_tuning",
                "detail": (
                    f"Average tokens {metrics['avg_tokens_per_run']} exceeds "
                    f"baseline {baseline_value:.0f} by >20%. Consider reducing "
                    "temperature or max_tokens."
                ),
                "requires_phase_d": True,
            }
        elif metrics["token_efficiency"] < 0.5:
            metric = "token_efficiency"
            before_value = metrics["token_efficiency"]
            after_value = baseline_value
            adjustment = {
                "suggestion": "tool_selection_improvement",
                "detail": (
                    f"Token efficiency {metrics['token_efficiency']:.1%} is below 50%. "
                    "Consider better agent/tool selection or simpler prompts."
                ),
                "requires_phase_d": True,
            }
        else:
            # Everything looks good — log a no-op optimization
            metric = "success_rate"
            before_value = metrics["success_rate"]
            after_value = metrics["success_rate"]
            adjustment = {
                "suggestion": "no_action_needed",
                "detail": "All metrics within acceptable ranges. No optimization required.",
                "requires_phase_d": False,
            }

        log = OptimizationLog(
            tenant_id=tenant_id,
            agent_type=agent_type,
            metric=metric,
            before_value=before_value,
            after_value=after_value,
            adjustment=adjustment,
        )
        db.add(log)
        await db.flush()
        return log

    @staticmethod
    async def get_optimization_history(
        db: AsyncSession,
        tenant_id: int,
        agent_type: str | None = None,
    ) -> list[OptimizationLog]:
        """Return optimization history for a tenant, optionally filtered by agent_type."""
        conditions = [OptimizationLog.tenant_id == tenant_id]
        if agent_type:
            conditions.append(OptimizationLog.agent_type == agent_type)

        stmt = (
            select(OptimizationLog)
            .where(*conditions)
            .order_by(OptimizationLog.created_at.desc())
        )
        rows = (await db.execute(stmt)).scalars().all()
        return list(rows)
