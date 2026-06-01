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


# ── Real job sources (free, no API key needed) ──────────────────────────

DEPLOYMENT_KEYWORDS = [
    "deploy", "devops", "kubernetes", "docker", "ci/cd", "infrastructure",
    "backend", "api", "fullstack", "python", "fastapi", "cloud",
    "site reliability", "platform engineer",
]

RELEVANT_TAGS = {
    "deploy", "devops", "docker", "kubernetes", "k8s", "python", "fastapi",
    "backend", "fullstack", "api", "node", "typescript", "react", "nextjs",
    "aws", "gcp", "cloud", "infrastructure", "ci/cd", "terraform", "helm",
    "linux", "nginx", "postgresql", "redis",
}


def _is_relevant(title: str, tags: list[str] | None, desc: str) -> bool:
    """Check if a job listing is relevant to CrossDeploy services."""
    if not title:
        return False
    ttl = title.lower()
    tag_set = {t.lower() for t in tags} if tags else set()
    text = f"{ttl} {desc[:500].lower()}"
    if tag_set & RELEVANT_TAGS:
        return True
    for kw in DEPLOYMENT_KEYWORDS:
        if kw in ttl or kw in text:
            return True
    return False


async def fetch_remoteok_api(keywords: list[str] | None = None) -> list[dict]:
    """Fetch real tech job listings from RemoteOK API (free, no auth)."""
    if keywords is None:
        keywords = DEPLOYMENT_KEYWORDS[:5]
    kw = "+".join(keywords[:3])
    url = f"https://remoteok.com/api?tag={kw}"
    jobs = []
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                    "Accept": "application/json",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                raw = data[1:] if isinstance(data, list) and len(data) > 1 else []
                for item in raw[:40]:
                    title = item.get("position", "").strip()
                    tags = item.get("tags", [])
                    desc = item.get("description", "")[:800]
                    if _is_relevant(title, tags, desc):
                        salary_min = item.get("salary_min")
                        salary_max = item.get("salary_max")
                        jobs.append({
                            "title": title,
                            "description": desc,
                            "platform": "remoteok",
                            "tags": tags[:5],
                            "salary_min": float(salary_min) if salary_min else None,
                            "salary_max": float(salary_max) if salary_max else None,
                            "source_url": item.get("url", ""),
                        })
                        if len(jobs) >= 10:  # cap at 10 relevant per source
                            break
            else:
                print(f"[scanner] RemoteOK returned {resp.status_code}")
    except Exception as e:
        print(f"[scanner] RemoteOK API fetch failed: {e}")
    return jobs


async def fetch_careernest_api() -> list[dict]:
    """Fetch devops/cloud jobs from Career Nest (free, no auth, 30 req/min).
    1.5M+ jobs, updated every 6h. Contract type often empty — query broad categories."""
    jobs = []
    try:
        import httpx
        urls = [
            "https://careernest.cloud/api/feed?category=devops-cloud&limit=30",
            "https://careernest.cloud/api/feed?category=software-development&limit=30",
        ]
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            for url in urls:
                resp = await client.get(
                    url,
                    headers={"User-Agent": "CrossWave/1.0 (order scanner)", "Accept": "application/json"},
                )
                if resp.status_code != 200:
                    continue
                cn_data = resp.json()
                if isinstance(cn_data, dict):
                    items = cn_data.get("jobs") or cn_data.get("data") or []
                elif isinstance(cn_data, list):
                    items = cn_data
                else:
                    items = []
                for item in items[:20]:
                    title = (item.get("title") or item.get("position") or item.get("job_title", "")).strip()
                    if not title:
                        continue
                    desc = (item.get("description") or item.get("summary", ""))[:800]
                    tags = item.get("tags") or item.get("skills", [])
                    tags_list = tags if isinstance(tags, list) else []
                    # Less strict — accept if title mentions any keyword
                    if _is_relevant(title, tags_list, desc) or any(k in title.lower() for k in ["engineer", "developer", "architect"]):
                        jobs.append({
                            "title": title,
                            "description": desc,
                            "platform": "careernest",
                            "tags": tags_list[:5],
                            "salary_min": None,
                            "salary_max": None,
                            "source_url": item.get("job_url") or item.get("url", ""),
                        })
    except Exception as e:
        print(f"[scanner] Career Nest API fetch failed: {e}")
    return jobs


async def fetch_remotejobs_api() -> list[dict]:
    """Fetch devops/contract jobs from RemoteJobs.org (free, no auth, no hard rate limit)."""
    jobs = []
    try:
        import httpx
        urls = [
            "https://remotejobs.org/api/v1/jobs?category=devops&type=contract&limit=20",
            "https://remotejobs.org/api/v1/jobs?category=programming&type=contract&limit=20",
        ]
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            for url in urls:
                resp = await client.get(
                    url,
                    headers={"User-Agent": "CrossWave/1.0", "Accept": "application/json"},
                )
                if resp.status_code != 200:
                    continue
                resp_data = resp.json()
                raw_items: list = []
                if isinstance(resp_data, dict):
                    for key in ("data", "jobs", "results"):
                        v = resp_data.get(key)
                        if isinstance(v, list):
                            raw_items = v
                            break
                elif isinstance(resp_data, list):
                    raw_items = resp_data
                for item in raw_items[:15]:
                    title = item.get("title", "").strip()
                    if not title:
                        continue
                    tags_raw = item.get("tags") or item.get("skills") or []
                    tags = tags_raw if isinstance(tags_raw, list) else []
                    desc = (item.get("description") or item.get("summary", ""))[:800]
                    if _is_relevant(title, tags, desc):
                        jobs.append({
                            "title": title,
                            "description": desc,
                            "platform": "remotejobs",
                            "tags": tags[:5],
                            "salary_min": None,
                            "salary_max": None,
                            "source_url": item.get("url") or item.get("apply_url", ""),
                        })
    except Exception as e:
        print(f"[scanner] RemoteJobs API fetch failed: {e}")
    return jobs


# ── Multi-source scanning ──────────────────────────────────────────────


async def _save_jobs(db: AsyncSession, jobs: list[dict], platform_map: str) -> list[ExternalOrder]:
    """Save a list of scanned jobs as ExternalOrder rows, deduplicating by title."""
    new_orders = []
    for job in jobs:
        exists = await db.execute(
            select(ExternalOrder).where(
                ExternalOrder.platform == platform_map,
                ExternalOrder.title == job["title"][:200],
            )
        )
        if exists.scalar_one_or_none():
            continue
        budget_min = job.get("salary_min") or random.randint(300, 3000)
        budget_max = job.get("salary_max") or budget_min * 2
        order = await create_order(
            db,
            title=job["title"][:200],
            platform=platform_map,
            external_id=job.get("source_url", "").split("/")[-1][:64] or f"{job['platform']}_{random.randint(10000, 99999)}",
            budget_min=budget_min,
            budget_max=budget_max,
            currency="USD",
            description=job.get("description", "")[:1000],
            source_url=job.get("source_url", ""),
        )
        new_orders.append(order)
    return new_orders


async def scan_platform(db: AsyncSession, platform: str) -> list[ExternalOrder]:
    """Scan a platform for new orders.
    For upwork: real sources (RemoteOK + Career Nest + RemoteJobs.org).
    For others: diversity pools + static templates."""
    new_orders = []

    if platform == "upwork":
        # 3 real sources in parallel
        real_sources = await asyncio.gather(
            fetch_remoteok_api(),
            fetch_careernest_api(),
            fetch_remotejobs_api(),
            return_exceptions=True,
        )
        for src_result in real_sources:
            if isinstance(src_result, BaseException):
                print(f"[scanner] Source failed: {src_result}")
                continue
            saved = await _save_jobs(db, src_result, platform)
            new_orders.extend(saved)

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
