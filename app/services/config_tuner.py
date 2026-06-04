"""Config tuner service — auto-applies optimization suggestions as AgentGenConfig versions.

Phase D: Bridges SelfOptimizerService (which generates suggestions) with the
AgentGenConfig ORM model. Handles versioned application, rollback, cooldown,
and the enable/disable gate.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.agent_gen_config import AgentGenConfig
from app.models.agent_run import AgentRun
from app.models.optimization_log import OptimizationLog


class ConfigTunerService:
    """Manages AgentGenConfig lifecycle — read, apply, revert, auto-tune.

    All methods are ``@staticmethod`` so they can be called without
    instantiation.
    """

    # ── Public API ──────────────────────────────────────────────────────────

    @staticmethod
    async def get_effective_config(
        db: AsyncSession,
        tenant_id: int,
        agent_type: str,
    ) -> dict:
        """Return the active AgentGenConfig as a plain dict.

        Returns ``{}`` when no config exists (NOT hardcoded defaults — let
        existing code use its own defaults).
        """
        stmt = (
            select(AgentGenConfig)
            .where(
                AgentGenConfig.tenant_id == tenant_id,
                AgentGenConfig.agent_type == agent_type,
                AgentGenConfig.is_active.is_(True),
            )
            .order_by(AgentGenConfig.version.desc())
            .limit(1)
        )
        config = (await db.execute(stmt)).scalar_one_or_none()
        if config is None:
            return {}
        return {
            "id": config.id,
            "tenant_id": config.tenant_id,
            "agent_type": config.agent_type,
            "version": config.version,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "top_p": config.top_p,
            "is_active": config.is_active,
            "applied_by": config.applied_by,
            "optimization_log_id": config.optimization_log_id,
            "rolled_back_at": config.rolled_back_at,
            "created_at": config.created_at,
        }

    @staticmethod
    async def apply_generation_config(
        db: AsyncSession,
        tenant_id: int,
        agent_type: str,
        suggestion: dict,
        optimization_log_id: int | None = None,
    ) -> AgentGenConfig:
        """Create a new AgentGenConfig version with tuned generation values.

        Calculates new values from the current baseline:
        - temperature = baseline_temp - 0.1  (min 0.1)
        - max_tokens  = baseline_tokens - 512  (min 512)

        Deactivates the previous active version before creating the new one.
        """
        # Grab baseline from the current effective config
        baseline = await ConfigTunerService.get_effective_config(
            db, tenant_id, agent_type,
        )

        base_temp: float = baseline.get("temperature") or 0.7
        base_tokens: int = baseline.get("max_tokens") or 2048
        base_top_p: float | None = baseline.get("top_p")

        new_temp = max(0.1, base_temp - 0.1)
        new_tokens = max(512, base_tokens - 512)

        # Determine next version number
        latest = await ConfigTunerService._latest_version(
            db, tenant_id, agent_type,
        )
        next_version = (latest.version + 1) if latest is not None else 1

        # Deactivate currently-active configs
        await ConfigTunerService._deactivate_all(db, tenant_id, agent_type)

        new_config = AgentGenConfig(
            tenant_id=tenant_id,
            agent_type=agent_type,
            version=next_version,
            temperature=new_temp,
            max_tokens=new_tokens,
            top_p=base_top_p,
            is_active=True,
            applied_by="auto_tune",
            optimization_log_id=optimization_log_id,
        )
        db.add(new_config)
        await db.flush()
        return new_config

    @staticmethod
    async def revert_config(
        db: AsyncSession,
        tenant_id: int,
        agent_type: str,
        target_version: int | None = None,
    ) -> AgentGenConfig:
        """Revert to a previous config version.

        When *target_version* is ``None``, rolls back to the previous version
        (the one with the highest version number below the current active).
        Sets ``rolled_back_at`` on deactivated configs for cooldown tracking.
        """
        if target_version is not None:
            target = await ConfigTunerService._get_by_version(
                db, tenant_id, agent_type, target_version,
            )
            if target is None:
                raise ValueError(
                    f"Version {target_version} not found for "
                    f"tenant={tenant_id} agent_type={agent_type}"
                )
        else:
            current = await ConfigTunerService.get_effective_config(
                db, tenant_id, agent_type,
            )
            if not current:
                raise ValueError(
                    f"No active config to revert from for "
                    f"tenant={tenant_id} agent_type={agent_type}"
                )
            target = await ConfigTunerService._previous_version(
                db, tenant_id, agent_type, current["version"],
            )
            if target is None:
                raise ValueError(
                    f"No previous version to revert to for "
                    f"tenant={tenant_id} agent_type={agent_type}"
                )

        # Deactivate currently-active configs and stamp rolled_back_at
        now = datetime.now(timezone.utc)
        await ConfigTunerService._deactivate_all(db, tenant_id, agent_type, rolled_back_at=now)

        # Activate the target
        target.is_active = True
        await db.flush()
        return target

    @staticmethod
    async def get_config_history(
        db: AsyncSession,
        tenant_id: int,
        agent_type: str | None = None,
    ) -> list[AgentGenConfig]:
        """Return all config versions for a tenant, newest first."""
        conditions = [AgentGenConfig.tenant_id == tenant_id]
        if agent_type:
            conditions.append(AgentGenConfig.agent_type == agent_type)

        stmt = (
            select(AgentGenConfig)
            .where(*conditions)
            .order_by(AgentGenConfig.created_at.desc())
        )
        rows = (await db.execute(stmt)).scalars().all()
        return list(rows)

    @staticmethod
    async def auto_tune(
        db: AsyncSession,
        tenant_id: int,
        agent_type: str,
        suggestion: dict,
    ) -> AgentGenConfig | None:
        """Auto-apply a generation-config suggestion.

        Guarded by:
        1. ``settings.config_tuner_enabled`` — master switch.
        2. **Cooldown**: if the most recently rolled-back config for this
           (tenant, agent_type) is less than 7 days old, skip.

        Returns the new ``AgentGenConfig`` or ``None`` when skipped.
        """
        if not settings.config_tuner_enabled:
            return None

        # Cooldown: any config rolled back less than 7 days ago?
        if await ConfigTunerService._in_cooldown(db, tenant_id, agent_type):
            return None

        return await ConfigTunerService.apply_generation_config(
            db,
            tenant_id=tenant_id,
            agent_type=agent_type,
            suggestion=suggestion,
        )

    @staticmethod
    async def check_and_rollback(
        db: AsyncSession,
        tenant_id: int,
        agent_type: str,
    ) -> bool:
        """Compare AgentRun metrics before & after the current active config.

        Requirements before evaluation:
        1. Active config exists.
        2. Not in cooldown (no rolled_back_at within 7 days).
        3. At least 5 AgentRun records *after* the config change.

        Thresholds (either triggers rollback):
        - **success_rate**: absolute drop >10 percentage points.
        - **avg_tokens**: relative increase >20 % from baseline.

        When a threshold is exceeded it calls :meth:`revert_config` and logs
        the event to ``OptimizationLog``.

        Returns ``True`` when a rollback was performed.
        """
        # 1. Active config must exist
        current = await ConfigTunerService.get_effective_config(
            db, tenant_id, agent_type,
        )
        if not current:
            return False

        # 2. Cooldown check
        if await ConfigTunerService._in_cooldown(db, tenant_id, agent_type):
            return False

        # 3. Baseline timestamp = when the current config was created
        config_obj = await ConfigTunerService._get_by_version(
            db, tenant_id, agent_type, current.get("version", 0),
        )
        if config_obj is None or config_obj.created_at is None:
            return False
        baseline_ts = config_obj.created_at

        # 4. Post-change records (≥5 required)
        post_stmt = (
            select(AgentRun)
            .where(
                AgentRun.tenant_id == tenant_id,
                AgentRun.agent_type == agent_type,
                AgentRun.started_at >= baseline_ts,
            )
            .order_by(AgentRun.started_at.desc())
        )
        post_rows = (await db.execute(post_stmt)).scalars().all()
        if len(post_rows) < 5:
            return False

        # 5. Pre-change baseline records
        pre_stmt = (
            select(AgentRun)
            .where(
                AgentRun.tenant_id == tenant_id,
                AgentRun.agent_type == agent_type,
                AgentRun.started_at < baseline_ts,
            )
            .order_by(AgentRun.started_at.desc())
        )
        pre_rows = (await db.execute(pre_stmt)).scalars().all()
        if not pre_rows:
            return False

        # 6. Calculate metrics
        pre_completed = sum(1 for r in pre_rows if r.status == "completed")
        pre_total = len(pre_rows)
        pre_sr = pre_completed / pre_total if pre_total > 0 else 0.0

        post_completed = sum(1 for r in post_rows if r.status == "completed")
        post_total = len(post_rows)
        post_sr = post_completed / post_total if post_total > 0 else 0.0

        pre_tok = [r.tokens_used for r in pre_rows if r.tokens_used is not None]
        post_tok = [r.tokens_used for r in post_rows if r.tokens_used is not None]

        pre_avg = sum(pre_tok) / len(pre_tok) if pre_tok else 0.0
        post_avg = sum(post_tok) / len(post_tok) if post_tok else 0.0

        # 7. Threshold evaluation
        sr_drop = (pre_sr - post_sr) * 100  # percentage points
        tok_pct = (
            ((post_avg - pre_avg) / pre_avg * 100) if pre_avg > 0 else 0.0
        )

        if sr_drop > 10:
            metric = "success_rate"
            before = round(pre_sr, 4)
            after = round(post_sr, 4)
        elif tok_pct > 20:
            metric = "avg_tokens"
            before = round(pre_avg, 2)
            after = round(post_avg, 2)
        else:
            return False  # No degradation detected

        # 8. Perform rollback
        await ConfigTunerService.revert_config(db, tenant_id, agent_type)

        # 9. Log rollback
        detail_parts = []
        if metric == "success_rate":
            detail_parts.append(
                f"Success rate dropped from {before*100:.1f}% "
                f"to {after*100:.1f}%."
            )
        else:
            detail_parts.append(
                f"Average tokens increased from {before:.0f} "
                f"to {after:.0f}."
            )
        log = OptimizationLog(
            tenant_id=tenant_id,
            agent_type=agent_type,
            metric=metric,
            before_value=before,
            after_value=after,
            adjustment={
                "suggestion": "rollback",
                "detail": (
                    f"Auto-detected degradation and rolled back from config "
                    f"version {current['version']}. {' '.join(detail_parts)}"
                ),
            },
        )
        db.add(log)
        await db.flush()
        return True

    # ── Internal helpers ────────────────────────────────────────────────────

    @staticmethod
    async def _latest_version(
        db: AsyncSession,
        tenant_id: int,
        agent_type: str,
    ) -> AgentGenConfig | None:
        """Return the highest-versioned config for this scope."""
        stmt = (
            select(AgentGenConfig)
            .where(
                AgentGenConfig.tenant_id == tenant_id,
                AgentGenConfig.agent_type == agent_type,
            )
            .order_by(AgentGenConfig.version.desc())
            .limit(1)
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def _previous_version(
        db: AsyncSession,
        tenant_id: int,
        agent_type: str,
        current_version: int,
    ) -> AgentGenConfig | None:
        """Return the config version immediately below *current_version*."""
        stmt = (
            select(AgentGenConfig)
            .where(
                AgentGenConfig.tenant_id == tenant_id,
                AgentGenConfig.agent_type == agent_type,
                AgentGenConfig.version < current_version,
            )
            .order_by(AgentGenConfig.version.desc())
            .limit(1)
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def _get_by_version(
        db: AsyncSession,
        tenant_id: int,
        agent_type: str,
        version: int,
    ) -> AgentGenConfig | None:
        stmt = (
            select(AgentGenConfig)
            .where(
                AgentGenConfig.tenant_id == tenant_id,
                AgentGenConfig.agent_type == agent_type,
                AgentGenConfig.version == version,
            )
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def _deactivate_all(
        db: AsyncSession,
        tenant_id: int,
        agent_type: str,
        rolled_back_at: datetime | None = None,
    ) -> None:
        """Deactivate every active config for this scope.

        If *rolled_back_at* is provided, stamp it on each deactivated row.
        """
        stmt = (
            select(AgentGenConfig)
            .where(
                AgentGenConfig.tenant_id == tenant_id,
                AgentGenConfig.agent_type == agent_type,
                AgentGenConfig.is_active.is_(True),
            )
        )
        rows = (await db.execute(stmt)).scalars().all()
        for cfg in rows:
            cfg.is_active = False
            if rolled_back_at is not None:
                cfg.rolled_back_at = rolled_back_at

    @staticmethod
    async def _in_cooldown(
        db: AsyncSession,
        tenant_id: int,
        agent_type: str,
        cooldown_days: int = 7,
    ) -> bool:
        """Return ``True`` if a rolled-back config is within *cooldown_days*."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=cooldown_days)
        stmt = (
            select(AgentGenConfig)
            .where(
                AgentGenConfig.tenant_id == tenant_id,
                AgentGenConfig.agent_type == agent_type,
                AgentGenConfig.rolled_back_at.is_not(None),
                AgentGenConfig.rolled_back_at >= cutoff,
            )
            .limit(1)
        )
        return (await db.execute(stmt)).scalar_one_or_none() is not None
