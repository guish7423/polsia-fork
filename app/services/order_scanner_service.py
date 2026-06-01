"""Order scanner service — simulate scraping and evaluate external orders."""

import json
import random
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.external_order import ExternalOrder


async def create_order(
    db: AsyncSession,
    title: str,
    platform: str = "internal",
    external_id: str | None = None,
    budget_min: float | None = None,
    budget_max: float | None = None,
    currency: str = "USD",
    description: str | None = None,
    requirements: str | None = None,
    source_url: str | None = None,
) -> ExternalOrder:
    order = ExternalOrder(
        title=title,
        platform=platform,
        external_id=external_id,
        budget_min=budget_min,
        budget_max=budget_max,
        currency=currency,
        description=description,
        requirements=requirements,
        source_url=source_url,
    )
    db.add(order)
    await db.flush()
    await db.refresh(order)
    return order


async def get_orders(
    db: AsyncSession,
    platform: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[ExternalOrder]:
    query = select(ExternalOrder).order_by(ExternalOrder.created_at.desc())
    if platform:
        query = query.where(ExternalOrder.platform == platform)
    if status:
        query = query.where(ExternalOrder.status == status)
    query = query.limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_order(db: AsyncSession, order_id: int) -> ExternalOrder | None:
    result = await db.execute(
        select(ExternalOrder).where(ExternalOrder.id == order_id)
    )
    return result.scalar_one_or_none()


async def update_order_status(
    db: AsyncSession,
    order_id: int,
    status: str,
    score: float | None = None,
    score_reason: str | None = None,
    assigned_agent: str | None = None,
) -> ExternalOrder | None:
    order = await get_order(db, order_id)
    if not order:
        return None
    order.status = status
    if score is not None:
        order.score = score
    if score_reason is not None:
        order.score_reason = score_reason
    if assigned_agent is not None:
        order.assigned_agent = assigned_agent
    if status in ("completed", "failed", "rejected"):
        order.completed_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(order)
    return order


async def get_orders_summary(db: AsyncSession) -> dict:
    result = await db.execute(
        select(ExternalOrder.status, func.count(ExternalOrder.id)).group_by(
            ExternalOrder.status
        )
    )
    rows = result.all()
    summary = {"total": sum(r[1] for r in rows)}
    for status, count in rows:
        summary[status] = count
    for s in ("scanned", "evaluated", "accepted", "in_progress", "completed", "failed", "rejected"):
        summary.setdefault(s, 0)
    return summary


PLATFORM_TEMPLATES: dict[str, list[dict]] = {
    "upwork": [
        {"title": "Python API integration for SaaS platform", "budget_min": 500, "budget_max": 3000, "desc": "Need a developer to integrate Stripe + Twilio APIs into existing FastAPI app"},
        {"title": "SEO content writer for AI blog (Chinese→English)", "budget_min": 200, "budget_max": 1500, "desc": "Looking for bilingual writer to create SEO-optimized blog posts about AI"},
        {"title": "Full-stack developer — Next.js + FastAPI dashboard", "budget_min": 2000, "budget_max": 8000, "desc": "Build admin dashboard with authentication, data viz, and user management"},
    ],
    "fiverr": [
        {"title": "Translate my SaaS landing page to Chinese", "budget_min": 50, "budget_max": 300, "desc": "Need professional Chinese translation for 5-page SaaS website"},
        {"title": "Set up CI/CD pipeline for my startup", "budget_min": 100, "budget_max": 500, "desc": "GitHub Actions + Docker + Railway deployment pipeline setup"},
        {"title": "Create 5 blog posts about AI for startups", "budget_min": 150, "budget_max": 600, "desc": "SEO-optimized blog posts about practical AI applications for small businesses"},
    ],
    "zhubajie": [
        {"title": "小程序开发 — AI 内容生成工具", "budget_min": 3000, "budget_max": 10000, "currency": "CNY", "desc": "开发一个基于 AI 的内容生成微信小程序"},
        {"title": "企业官网改版 — 科技公司 SaaS 风格", "budget_min": 5000, "budget_max": 20000, "currency": "CNY", "desc": "将传统企业网站改版为现代 SaaS 风格官网"},
    ],
}


async def scan_platform(db: AsyncSession, platform: str) -> list[ExternalOrder]:
    """Simulate scraping a platform for new orders."""
    templates = PLATFORM_TEMPLATES.get(platform, [])
    new_orders = []
    for t in templates:
        exists = await db.execute(
            select(ExternalOrder).where(
                ExternalOrder.platform == platform,
                ExternalOrder.title == t["title"],
            )
        )
        if exists.scalar_one_or_none():
            continue
        order = await create_order(
            db,
            title=t["title"],
            platform=platform,
            external_id=f"{platform}_{random.randint(10000, 99999)}",
            budget_min=t.get("budget_min"),
            budget_max=t.get("budget_max"),
            currency=t.get("currency", "USD"),
            description=t.get("desc"),
        )
        new_orders.append(order)
    return new_orders
