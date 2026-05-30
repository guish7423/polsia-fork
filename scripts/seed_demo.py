"""Seed rich demo data — tasks, activity, finance, agent runs.

Usage:
    python scripts/seed_demo.py                  # uses DATABASE_URL from env
    python scripts/seed_demo.py --fresh          # drop and recreate first
"""
import asyncio
import sys
import os
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.config import settings
from app.models.base import Base

# ─── Model imports ──────────────────────────────────────────────────────────
from app.models.company_config import CompanyConfig
from app.models.task import Task
from app.models.activity_log import ActivityLog
from app.models.finance import RevenueSnapshot, ExpenseRecord
from app.models.agent_run import AgentRun

AGENTS = [
    "orchestrator", "business_planning", "competitor_research",
    "social_media", "email_outreach", "customer_support",
    "ads_management", "code_generation", "finance", "deployment",
]

TASK_TEMPLATES: list[dict] = [
    {"agent_type": "orchestrator", "title": "Morning planning cycle", "priority": 1, "status": "completed", "source": "system"},
    {"agent_type": "orchestrator", "title": "Evening summary & metrics review", "priority": 1, "status": "completed", "source": "system"},
    {"agent_type": "orchestrator", "title": "Assign weekly goals to team agents", "priority": 2, "status": "pending", "source": "system"},
    {"agent_type": "orchestrator", "title": "Cross-agent sync: resolve task conflicts", "priority": 3, "status": "failed", "source": "system",
     "error_message": "Conflict detected: social_media and email_outreach both scheduled at 09:00"},
    {"agent_type": "business_planning", "title": "Q3 growth strategy: market expansion", "priority": 1, "status": "pending", "source": "orchestrator"},
    {"agent_type": "business_planning", "title": "Competitive landscape quarterly review", "priority": 2, "status": "completed", "source": "orchestrator"},
    {"agent_type": "business_planning", "title": "Refine OKRs based on last month data", "priority": 2, "status": "pending", "source": "orchestrator"},
    {"agent_type": "business_planning", "title": "Board deck: Q2 results summary", "priority": 1, "status": "completed", "source": "orchestrator"},
    {"agent_type": "competitor_research", "title": "Scan competitor X: feature parity analysis", "priority": 2, "status": "completed", "source": "orchestrator"},
    {"agent_type": "competitor_research", "title": "Monitor price changes across top 5 competitors", "priority": 2, "status": "completed", "source": "system"},
    {"agent_type": "competitor_research", "title": "Industry report: AI SaaS benchmarks 2026", "priority": 3, "status": "pending", "source": "business_planning"},
    {"agent_type": "competitor_research", "title": "New entrant analysis: startup Clarity AI", "priority": 2, "status": "completed", "source": "orchestrator"},
    {"agent_type": "social_media", "title": "Draft weekly LinkedIn thought leadership post", "priority": 2, "status": "completed", "source": "orchestrator"},
    {"agent_type": "social_media", "title": "Schedule X thread: AI industry trends", "priority": 3, "status": "completed", "source": "orchestrator"},
    {"agent_type": "social_media", "title": "Engage with top 10 mentions from this week", "priority": 4, "status": "pending", "source": "system"},
    {"agent_type": "social_media", "title": "Create Instagram carousel: product features", "priority": 3, "status": "failed", "source": "orchestrator",
     "error_message": "Image generation timeout — API rate limit exceeded"},
    {"agent_type": "email_outreach", "title": "Send cold email batch to 120 leads (segment A)", "priority": 2, "status": "completed", "source": "orchestrator"},
    {"agent_type": "email_outreach", "title": "A/B test subject lines for Q3 campaign", "priority": 3, "status": "completed", "source": "orchestrator"},
    {"agent_type": "email_outreach", "title": "Follow-up sequence: week 2 non-responders", "priority": 2, "status": "pending", "source": "system"},
    {"agent_type": "customer_support", "title": "Ticket triage: process 23 overnight tickets", "priority": 1, "status": "completed", "source": "system"},
    {"agent_type": "customer_support", "title": "Escalated: API outage — respond to 5 urgent tickets", "priority": 1, "status": "completed", "source": "system"},
    {"agent_type": "customer_support", "title": "Update knowledge base: new integration guide", "priority": 4, "status": "pending", "source": "orchestrator"},
    {"agent_type": "customer_support", "title": "Customer satisfaction survey: send to NPS detractors", "priority": 3, "status": "completed", "source": "orchestrator"},
    {"agent_type": "ads_management", "title": "Optimize Google Ads budget: redistribute $2K", "priority": 2, "status": "completed", "source": "orchestrator"},
    {"agent_type": "ads_management", "title": "Launch LinkedIn retargeting campaign", "priority": 2, "status": "pending", "source": "orchestrator"},
    {"agent_type": "ads_management", "title": "A/B test ad creative: 4 variants", "priority": 3, "status": "completed", "source": "orchestrator"},
    {"agent_type": "ads_management", "title": "Monthly ad performance report", "priority": 3, "status": "completed", "source": "finance"},
    {"agent_type": "code_generation", "title": "Fix billing calculation rounding error (#892)", "priority": 1, "status": "completed", "source": "customer_support",
     "result_summary": "Fixed round-to-nearest instead of floor on tax calculation"},
    {"agent_type": "code_generation", "title": "Implement CSV export for dashboard", "priority": 3, "status": "pending", "source": "orchestrator"},
    {"agent_type": "code_generation", "title": "Refactor notification service for scalability", "priority": 4, "status": "completed", "source": "orchestrator"},
    {"agent_type": "code_generation", "title": "Add rate limiting middleware to API gateway", "priority": 2, "status": "completed", "source": "orchestrator"},
    {"agent_type": "finance", "title": "Generate weekly revenue report", "priority": 1, "status": "completed", "source": "system"},
    {"agent_type": "finance", "title": "Reconcile Stripe payouts: June batch", "priority": 1, "status": "pending", "source": "system"},
    {"agent_type": "finance", "title": "Q2 expense analysis & budget reforecast", "priority": 2, "status": "completed", "source": "business_planning"},
    {"agent_type": "finance", "title": "Invoice client: Premium Plan Q2 (3 accounts)", "priority": 2, "status": "completed", "source": "system"},
    {"agent_type": "deployment", "title": "Deploy v2.1.0 to production (staging verified)", "priority": 1, "status": "completed", "source": "code_generation"},
    {"agent_type": "deployment", "title": "Rollback: v2.1.1 incident — database migration conflict", "priority": 1, "status": "failed", "source": "monitoring",
     "error_message": "Migration `add_billing_columns` ran out of order — hotfix required"},
    {"agent_type": "deployment", "title": "Provision staging environment for client onboarding", "priority": 3, "status": "pending", "source": "orchestrator"},
    {"agent_type": "deployment", "title": "SSL certificate renewal (3 domains expire in 7d)", "priority": 1, "status": "completed", "source": "system"},
]

ACTIVITY_TEMPLATES: list[dict] = [
    {"agent_type": "orchestrator", "action": "plan", "summary": "Planned 12 tasks for today", "level": "info"},
    {"agent_type": "orchestrator", "action": "assign", "summary": "Assigned competitive analysis to Research Agent", "level": "info"},
    {"agent_type": "orchestrator", "action": "review", "summary": "Reviewed evening reports from all 10 agents", "level": "info"},
    {"agent_type": "business_planning", "action": "analyze", "summary": "Completed Q3 growth strategy draft", "level": "info"},
    {"agent_type": "business_planning", "action": "report", "summary": "Generated quarterly competitive landscape report", "level": "info"},
    {"agent_type": "competitor_research", "action": "scan", "summary": "Detected price reduction by Competitor X (15% drop)", "level": "warning"},
    {"agent_type": "competitor_research", "action": "alert", "summary": "Competitor Y launched new AI analytics feature", "level": "warning"},
    {"agent_type": "social_media", "action": "publish", "summary": "Posted to LinkedIn: 'Building AI Agents for Business'", "level": "info"},
    {"agent_type": "social_media", "action": "publish", "summary": "Posted to X: weekly AI market insights thread", "level": "info"},
    {"agent_type": "social_media", "action": "engage", "summary": "Responded to 12 mentions and comments", "level": "info"},
    {"agent_type": "social_media", "action": "error", "summary": "Instagram posting failed: media upload timeout", "level": "error"},
    {"agent_type": "email_outreach", "action": "send", "summary": "Sent 45 cold emails to leads (segment A)", "level": "info"},
    {"agent_type": "email_outreach", "action": "analyze", "summary": "Open rate 38.2% — A/B test variant B winning", "level": "info"},
    {"agent_type": "email_outreach", "action": "follow_up", "summary": "Follow-up sequence triggered for 28 non-responders", "level": "info"},
    {"agent_type": "customer_support", "action": "resolve", "summary": "Answered ticket #1423: API integration question", "level": "info"},
    {"agent_type": "customer_support", "action": "resolve", "summary": "Answered ticket #1427: Billing discrepancy", "level": "info"},
    {"agent_type": "customer_support", "action": "escalate", "summary": "Escalated ticket #1431: Production outage (P0)", "level": "error"},
    {"agent_type": "customer_support", "action": "resolve", "summary": "Auto-reply to 6 common FAQ tickets", "level": "info"},
    {"agent_type": "ads_management", "action": "optimize", "summary": "Google Ads budget reallocated: +22% ROI improvement", "level": "info"},
    {"agent_type": "ads_management", "action": "launch", "summary": "Launched LinkedIn retargeting campaign (budget: $1,500)", "level": "info"},
    {"agent_type": "ads_management", "action": "report", "summary": "Monthly ad performance: $0.45 avg CPC, 2.8% CTR", "level": "info"},
    {"agent_type": "code_generation", "action": "commit", "summary": "Pushed fix for billing calculation rounding error", "level": "info"},
    {"agent_type": "code_generation", "action": "commit", "summary": "Refactored notification service — 40% latency reduction", "level": "info"},
    {"agent_type": "code_generation", "action": "review", "summary": "Code review: PR #234 — rate limiting middleware", "level": "info"},
    {"agent_type": "finance", "action": "report", "summary": "Weekly revenue report: $19,200 MRR (+3.2% WoW)", "level": "info"},
    {"agent_type": "finance", "action": "reconcile", "summary": "Stripe reconciliation: $4,200 pending payout", "level": "info"},
    {"agent_type": "finance", "action": "invoice", "summary": "Invoiced Premium Plan Q2: 3 accounts @ $499/mo", "level": "info"},
    {"agent_type": "deployment", "action": "deploy", "summary": "Deployed v2.1.0 to production (zero-downtime)", "level": "info"},
    {"agent_type": "deployment", "action": "rollback", "summary": "Emergency rollback v2.1.1: migration conflict", "level": "error"},
    {"agent_type": "deployment", "action": "provision", "summary": "SSL certificates renewed for 3 domains", "level": "info"},
    {"agent_type": "deployment", "action": "scale", "summary": "Auto-scaled backend from 2→4 replicas (load spike)", "level": "warning"},
]

TODAY = date.today()


async def seed_demo(engine, fresh: bool = False):
    """Seed all demo data."""
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    if fresh:
        tables = ["agent_runs", "activity_log", "expense_records", "revenue_snapshots", "tasks", "company_config"]
        async with engine.begin() as conn:
            for tbl in tables:
                await conn.execute(text(f"DROP TABLE IF EXISTS {tbl}"))
            await conn.run_sync(Base.metadata.create_all)

    async with Session() as session:
        # ── 1. Company Config ──────────────────────────────────────────────
        result = await session.execute(
            __import__("sqlalchemy").select(CompanyConfig).limit(1)
        )
        existing = result.scalar_one_or_none()
        if existing:
            print("✓ Company config already exists")
        else:
            company = CompanyConfig(
                name="CrossWave Technologies",
                mission="Empower businesses with autonomous AI agents that work 24/7.",
                vision="Become the leading autonomous AI operations platform for SMBs globally.",
                description="CrossWave is a self-hosted AI platform that automates marketing, sales, support, and engineering operations.",
                target_market="SaaS companies with 5-50 employees seeking operational automation.",
                value_prop="Deploy 10 specialized AI agents that run your daily operations — saving 20+ hours/week.",
                pricing_model={
                    "plans": [
                        {"name": "Starter", "price": 499, "agents": 3, "tasks_per_day": 50},
                        {"name": "Pro", "price": 1499, "agents": 10, "tasks_per_day": 200},
                        {"name": "Enterprise", "price": None, "agents": "Unlimited", "tasks_per_day": "Custom"},
                    ]
                },
                goals={
                    "q3_2026": ["Hit $25K MRR", "50 paying customers", "Launch CrossBlog integration"],
                    "q4_2026": ["$50K MRR", "150 customers", "Enterprise SSO + compliance"],
                },
                kpis={
                    "mrr_usd": 19200,
                    "active_customers": 38,
                    "churn_rate": 2.1,
                    "cac_usd": 1200,
                    "ltv_usd": 14400,
                    "nps": 42,
                },
                website_url="https://crosswave.app",
                github_repo="guish7423/crosswave",
                product_type="SaaS",
                industry="AI / Automation",
                timezone="Asia/Shanghai",
                daily_cycle_hour=6,
            )
            session.add(company)
            print("✓ Company config seeded")

        await session.commit()

    async with Session() as session:
        # ── 2. Tasks (38 entries across all agents) ────────────────────────
        task_count = (await session.execute(
            __import__("sqlalchemy").select(__import__("sqlalchemy").func.count()).select_from(Task)
        )).scalar()
        if task_count > 0:
            print(f"✓ {task_count} tasks already exist")
        else:
            for i, t in enumerate(TASK_TEMPLATES):
                task = Task(
                    title=t["title"],
                    description=None,
                    agent_type=t["agent_type"],
                    priority=t.get("priority", 3),
                    status=t.get("status", "pending"),
                    source=t.get("source", "orchestrator"),
                    scheduled_date=datetime.now(timezone.utc) - timedelta(hours=len(TASK_TEMPLATES) - i),
                    result_summary=t.get("result_summary"),
                    error_message=t.get("error_message"),
                )
                session.add(task)
            await session.commit()
            print(f"✓ {len(TASK_TEMPLATES)} tasks seeded")

    async with Session() as session:
        # ── 3. Activity Log (31 entries, staggered over last 24h) ──────────
        act_count = (await session.execute(
            __import__("sqlalchemy").select(__import__("sqlalchemy").func.count()).select_from(ActivityLog)
        )).scalar()
        if act_count > 0:
            print(f"✓ {act_count} activity logs already exist")
        else:
            now = datetime.now(timezone.utc)
            for i, a in enumerate(ACTIVITY_TEMPLATES):
                log = ActivityLog(
                    agent_type=a["agent_type"],
                    action=a["action"],
                    summary=a["summary"],
                    level=a.get("level", "info"),
                    created_at=now - timedelta(minutes=len(ACTIVITY_TEMPLATES) - i),
                )
                session.add(log)
            await session.commit()
            print(f"✓ {len(ACTIVITY_TEMPLATES)} activity logs seeded")

    async with Session() as session:
        # ── 4. Revenue Snapshots (30 days of growth trend) ─────────────────
        rev_count = (await session.execute(
            __import__("sqlalchemy").select(__import__("sqlalchemy").func.count()).select_from(RevenueSnapshot)
        )).scalar()
        if rev_count > 0:
            print(f"✓ {rev_count} revenue snapshots already exist")
        else:
            base_mrr = 120_00  # $120.00 → $19,200 over 30 days
            base_subs = 3
            for day_offset in range(30, -1, -1):
                d = TODAY - timedelta(days=day_offset)
                growth = 1 + (30 - day_offset) * 0.015  # 1.5% daily growth
                snapshot = RevenueSnapshot(
                    snapshot_date=d,
                    mrr_cents=int(base_mrr * growth),
                    arr_cents=int(base_mrr * growth * 12),
                    active_subscribers=max(base_subs, int(base_subs * growth)),
                    churned_today=0 if day_offset % 7 else 1,
                    new_today=1 if day_offset < 28 else 0,
                )
                session.add(snapshot)
            # Also add expenses
            expense_categories = [
                ("hosting", "Railway", 12000, "Production hosting: API + DB + Redis"),
                ("hosting", "Fly.io", 15000, "Secondary region: Hong Kong deployment"),
                ("ai", "DeepSeek API", 8500, "LLM inference credits"),
                ("ai", "OpenAI API", 3200, "Embeddings + fallback model"),
                ("tools", "GitHub Copilot", 1200, "Team seat × 4"),
                ("tools", "Stripe Fees", 3800, "Payment processing: 2.9% + $0.30"),
                ("tools", "SendGrid", 1500, "Email API: 50K/mo plan"),
                ("infra", "Cloudflare", 800, "DNS + CDN + WAF"),
            ]
            for cat, vendor, cents, desc in expense_categories:
                session.add(ExpenseRecord(
                    category=cat, vendor=vendor,
                    amount_cents=cents, description=desc,
                    date=TODAY,
                ))
            await session.commit()
            print(f"✓ 31 revenue snapshots + 8 expense records seeded")

    async with Session() as session:
        # ── 5. Agent Runs ──────────────────────────────────────────────────
        run_count = (await session.execute(
            __import__("sqlalchemy").select(__import__("sqlalchemy").func.count()).select_from(AgentRun)
        )).scalar()
        if run_count > 0:
            print(f"✓ {run_count} agent runs already exist")
        else:
            now = datetime.now(timezone.utc)
            for i, agent in enumerate(AGENTS):
                for run_idx in range(2, -1, -1):
                    cost = 0.05 + (i * 0.02) + (run_idx * 0.01)
                    duration = 30 + (i * 5) + (run_idx * 10)
                    run = AgentRun(
                        agent_type=agent,
                        run_type="task",
                        status="completed",
                        tokens_used=int(cost * 100000),
                        cost_usd=round(cost, 4),
                        duration_secs=float(duration),
                        started_at=now - timedelta(hours=i * 2 + run_idx * 4),
                        ended_at=now - timedelta(hours=i * 2 + run_idx * 4) + timedelta(seconds=duration),
                    )
                    session.add(run)
            await session.commit()
            print(f"✓ 30 agent runs seeded")

    print("\n✅ Demo data complete! Start the server and check /dashboard:")
    print(f"   DATABASE_URL={settings.database_url}")
    print("   API_KEY=dev-key")
    print("   → curl -H 'X-API-Key: dev-key' http://localhost:8000/api/v1/dashboard/summary")


async def main():
    fresh = "--fresh" in sys.argv
    engine = create_async_engine(settings.database_url, echo=False)
    try:
        await seed_demo(engine, fresh=fresh)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
