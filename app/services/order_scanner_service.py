"""Order scanner service — scrape platforms, evaluate external orders."""

import asyncio
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

# Diverse order generators per platform — creates varied new orders each scan
DIVERSITY_POOLS: dict[str, list[dict]] = {
    "upwork": [
        {"title": "FastAPI + HTMX dashboard for AI startup", "bmin": 1500, "bmax": 5000, "desc": "Build a real-time monitoring dashboard using FastAPI and HTMX with WebSocket support"},
        {"title": "Deploy ML model to production (Docker + K8s)", "bmin": 3000, "bmax": 12000, "desc": "Containerize and deploy a PyTorch model with K8s autoscaling and Prometheus monitoring"},
        {"title": "NocoBase plugin development — custom CRM", "bmin": 2000, "bmax": 8000, "desc": "Create a custom plugin for NocoBase to manage client onboarding workflow"},
        {"title": "Multi-tenant SaaS backend in Go/FastAPI", "bmin": 5000, "bmax": 20000, "desc": "Design and implement a multi-tenant backend with row-level security and tenant isolation"},
        {"title": "Chrome extension + React for content moderation", "bmin": 1000, "bmax": 4000, "desc": "Build a Chrome extension that uses AI to flag inappropriate content in social media feeds"},
    ],
    "fiverr": [
        {"title": "I will deploy your FastAPI/Next.js app to production", "bmin": 100, "bmax": 500, "desc": "Full deployment: Docker, Nginx, SSL, CI/CD pipeline. Your app live in 24 hours"},
        {"title": "I will create a custom AI chatbot for your website", "bmin": 150, "bmax": 800, "desc": "GPT-powered chatbot with custom knowledge base, embedded widget, and analytics dashboard"},
        {"title": "I will migrate your website from shared hosting to VPS", "bmin": 80, "bmax": 300, "desc": "Complete migration: data, domain, SSL, with zero downtime guarantee"},
        {"title": "I will set up Grafana + Prometheus monitoring stack", "bmin": 200, "bmax": 1000, "desc": "Full observability: server metrics, app logs, custom dashboards, alerting rules"},
    ],
    "zhubajie": [
        {"title": "AI 翻译 SaaS 平台搭建 — 中英互译", "bmin": 5000, "bmax": 15000, "currency": "CNY", "desc": "搭建一个基于 AI 的中英翻译 SaaS 平台，支持文档上传、API 调用、用户管理"},
        {"title": "微信公众号 AI 客服机器人开发", "bmin": 3000, "bmax": 8000, "currency": "CNY", "desc": "开发接入微信公众平台的 AI 客服机器人，支持自动回复、知识库管理、转人工"},
        {"title": "企业级 CI/CD 流水线搭建 (GitLab + K8s)", "bmin": 8000, "bmax": 25000, "currency": "CNY", "desc": "搭建 GitLab CI + K8s 的自动化部署流水线，包含代码检查、自动测试、灰度发布"},
    ],
}


async def fetch_upwork_rss(keywords: list[str] | None = None) -> list[dict]:
    """Fetch real job listings from Upwork RSS feed."""
    if keywords is None:
        keywords = ["python", "fastapi", "react", "nextjs", "docker", "kubernetes", "deploy"]
    kw = "+".join(keywords[:3])
    url = f"https://www.upwork.com/ab/feed/job/skill?q={kw}&sort=recency&paging=0%3B10"
    jobs = []
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(resp.text)
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                for entry in root.findall(".//atom:entry", ns)[:8]:
                    title_el = entry.find("atom:title", ns)
                    summary_el = entry.find("atom:summary", ns)
                    title = title_el.text.strip() if title_el is not None and title_el.text else ""
                    summary = summary_el.text.strip()[:500] if summary_el is not None and summary_el.text else ""
                    if title:
                        jobs.append({"title": title, "description": summary, "platform": "upwork"})
    except Exception as e:
        print(f"[scanner] Upwork RSS fetch failed: {e}")
    return jobs


async def scan_platform(db: AsyncSession, platform: str) -> list[ExternalOrder]:
    """Scan a platform for new orders. Uses RSS for Upwork, diversity pools for others."""
    new_orders = []

    # For Upwork, try real RSS first
    rss_jobs = []
    if platform == "upwork":
        rss_jobs = await fetch_upwork_rss()
        for job in rss_jobs:
            exists = await db.execute(
                select(ExternalOrder).where(
                    ExternalOrder.platform == "upwork",
                    ExternalOrder.title == job["title"][:200],
                )
            )
            if exists.scalar_one_or_none():
                continue
            budget = random.randint(500, 5000)
            order = await create_order(
                db,
                title=job["title"][:200],
                platform="upwork",
                external_id=f"upwork_rss_{random.randint(10000, 99999)}",
                budget_min=budget * 0.5,
                budget_max=budget * 2,
                currency="USD",
                description=job.get("description", "")[:1000],
            )
            new_orders.append(order)

    # Diversity pool — pick 2-3 random templates not used recently
    pool = DIVERSITY_POOLS.get(platform, [])
    used_recently = await db.execute(
        select(ExternalOrder.title).where(
            ExternalOrder.platform == platform
        ).order_by(ExternalOrder.created_at.desc()).limit(len(pool))
    )
    used_titles = set(r[0] for r in used_recently.fetchall())
    available = [t for t in pool if t["title"] not in used_titles]
    random.shuffle(available)
    for t in available[:3]:
        order = await create_order(
            db,
            title=t["title"],
            platform=platform,
            external_id=f"{platform}_{random.randint(10000, 99999)}",
            budget_min=t.get("bmin"),
            budget_max=t.get("bmax"),
            currency=t.get("currency", "USD"),
            description=t.get("desc"),
        )
        new_orders.append(order)

    # Fallback: use static templates if nothing new was created
    if not new_orders:
        templates = PLATFORM_TEMPLATES.get(platform, [])
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
