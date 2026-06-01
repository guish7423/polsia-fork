"""Evolution Office — analyzes agent performance and drives self-improvement."""

import time
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_log import ActivityLog
from app.models.task import Task
from app.models.lead import Lead
from app.models.external_order import ExternalOrder
from app.agents.base import agent_map


async def get_agent_performance(
    db: AsyncSession, days: int = 7
) -> dict:
    """Analyze agent performance over the last N days.

    Returns dict with per-agent metrics, trends, and improvement suggestions.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # 1. Activity log analysis
    act_result = await db.execute(
        select(ActivityLog)
        .where(ActivityLog.created_at >= since)
        .order_by(ActivityLog.created_at.desc())
    )
    activities = list(act_result.scalars().all())

    # 2. Task analysis
    task_result = await db.execute(
        select(Task)
        .where(Task.created_at >= since)
    )
    tasks = list(task_result.scalars().all())

    # 3. Lead analysis
    lead_result = await db.execute(
        select(Lead)
        .where(Lead.created_at >= since)
    )
    leads = list(lead_result.scalars().all())

    # 4. External order analysis
    order_result = await db.execute(
        select(ExternalOrder)
        .where(ExternalOrder.created_at >= since)
    )
    ext_orders = list(order_result.scalars().all())

    # Per-agent metrics from activity_log
    agent_metrics = {}
    for act in activities:
        at = act.agent_type or "unknown"
        if at not in agent_metrics:
            agent_metrics[at] = {
                "agent_type": at,
                "total_runs": 0,
                "error_count": 0,
                "warning_count": 0,
                "info_count": 0,
                "actions": {},
                "last_run": None,
                "first_run": None,
            }
        agent_metrics[at]["total_runs"] += 1
        if act.level == "error":
            agent_metrics[at]["error_count"] += 1
        elif act.level == "warning":
            agent_metrics[at]["warning_count"] += 1
        else:
            agent_metrics[at]["info_count"] += 1
        action = act.action or "unknown"
        agent_metrics[at]["actions"][action] = agent_metrics[at]["actions"].get(action, 0) + 1
        created_str = str(act.created_at) if act.created_at else None
        if created_str:
            if not agent_metrics[at]["last_run"] or created_str > agent_metrics[at]["last_run"]:
                agent_metrics[at]["last_run"] = created_str
            if not agent_metrics[at]["first_run"] or created_str < agent_metrics[at]["first_run"]:
                agent_metrics[at]["first_run"] = created_str

    # Per-agent metrics from tasks
    task_metrics = {}
    for t in tasks:
        at = t.agent_type or "unknown"
        if at not in task_metrics:
            task_metrics[at] = {"assigned": 0, "completed": 0, "failed": 0, "pending": 0}
        task_metrics[at]["assigned"] += 1
        status = t.status or "pending"
        if status in ("done", "completed"):
            task_metrics[at]["completed"] += 1
        elif status == "failed":
            task_metrics[at]["failed"] += 1
        else:
            task_metrics[at]["pending"] += 1

    # Calculate success rates
    for at in agent_metrics:
        total = agent_metrics[at]["total_runs"]
        errors = agent_metrics[at]["error_count"]
        agent_metrics[at]["success_rate"] = round(
            (total - errors) / total * 100, 1
        ) if total else 0.0

    # Registered vs active analysis
    registered = set(agent_map.keys())
    active = set(m["agent_type"] for m in agent_metrics.values() if m["total_runs"] > 0)
    inactive_agents = sorted(registered - active)

    # Generate improvement suggestions
    suggestions = []
    for at, m in sorted(agent_metrics.items()):
        if m["success_rate"] < 70 and m["total_runs"] >= 3:
            suggestions.append(
                f"{at}: 成功率 {m['success_rate']}% ({m['error_count']}/{m['total_runs']} 错误) "
                f"— 建议审查提示词和输入质量"
            )
        if at in task_metrics:
            tm = task_metrics[at]
            if tm["assigned"] > 0 and tm["failed"] / tm["assigned"] > 0.3:
                suggestions.append(
                    f"{at}: 任务失败率 {round(tm['failed']/tm['assigned']*100)}% "
                    f"({tm['failed']}/{tm['assigned']}) — 建议检查任务类型匹配"
                )

    if not suggestions:
        suggestions.append("所有 Agent 运行正常，无需优化")

    return {
        "period_days": days,
        "agent_metrics": sorted(agent_metrics.values(), key=lambda x: -x["total_runs"]),
        "task_metrics": task_metrics,
        "inactive_agents": inactive_agents,
        "suggestions": suggestions,
        "total_activities": len(activities),
        "total_tasks": len(tasks),
        "total_leads": len(leads),
        "total_orders": len(ext_orders),
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }


async def generate_improvement_plan(
    db: AsyncSession, performance: dict
) -> dict:
    """Generate concrete improvement actions based on performance data.

    This function creates a structured improvement plan without LLM dependency.
    """
    plan = {
        "priority_actions": [],
        "config_adjustments": [],
        "agent_training": [],
        "monitoring_recommendations": [],
    }

    # Priority: agents with high error rates
    for m in performance.get("agent_metrics", []):
        if m["success_rate"] < 70 and m["total_runs"] >= 3:
            plan["priority_actions"].append(
                f"Review {m['agent_type']} agent — success rate {m['success_rate']}%"
            )

    # Priority: inactive agents
    for agent_name in performance.get("inactive_agents", []):
        plan["agent_training"].append(
            f"Consider removing or re-purposing unused agent: {agent_name}"
        )

    # Schedule adjustments
    if performance.get("total_activities", 0) == 0:
        plan["config_adjustments"].append(
            "No agent activity detected — verify Celery Beat schedules are running"
        )

    return plan
