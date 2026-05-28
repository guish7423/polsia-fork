"""Company configuration CRUD service."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company_config import CompanyConfig


async def get_company(db: AsyncSession) -> CompanyConfig | None:
    """Get the single company config (singleton pattern)."""
    result = await db.execute(select(CompanyConfig).limit(1))
    return result.scalar_one_or_none()


async def create_company(
    db: AsyncSession, name: str, mission: str | None = None,
    vision: str | None = None, description: str | None = None,
    target_market: str | None = None, value_prop: str | None = None,
    product_type: str | None = None, industry: str | None = None,
) -> CompanyConfig:
    """Create initial company configuration."""
    config = CompanyConfig(
        name=name, mission=mission, vision=vision,
        description=description, target_market=target_market,
        value_prop=value_prop, product_type=product_type,
        industry=industry,
    )
    db.add(config)
    await db.flush()
    return config


async def update_company(
    db: AsyncSession, company_id: int, **kwargs
) -> CompanyConfig | None:
    """Update company config fields."""
    config = await db.get(CompanyConfig, company_id)
    if not config:
        return None
    for key, value in kwargs.items():
        if hasattr(config, key) and value is not None:
            setattr(config, key, value)
    await db.flush()
    return config


async def get_full_context(db: AsyncSession) -> dict:
    """Get full company context dict for agent prompts."""
    company = await get_company(db)
    if not company:
        return {}
    return {
        "company": {
            "name": company.name,
            "mission": company.mission,
            "vision": company.vision,
            "description": company.description,
            "target_market": company.target_market,
            "value_prop": company.value_prop,
            "product_type": company.product_type,
            "industry": company.industry,
        },
        "kpis": company.kpis or {},
        "yesterday_summary": company.yesterday_summary or "",
    }


def build_context_prompt(context: dict) -> str:
    """Build a formatted context prompt string from the context dict."""
    if not context or "company" not in context:
        return "No company context available."
    parts = []
    company = context.get("company", {})
    parts.append(f"Company: {company.get('name', 'Unknown')}")
    if company.get("mission"):
        parts.append(f"Mission: {company['mission']}")
    if company.get("description"):
        parts.append(f"Description: {company['description']}")
    if company.get("target_market"):
        parts.append(f"Target Market: {company['target_market']}")
    if company.get("value_prop"):
        parts.append(f"Value Proposition: {company['value_prop']}")
    kpis = context.get("kpis", {})
    if kpis:
        parts.append(f"KPIs: {kpis}")
    yesterday = context.get("yesterday_summary")
    if yesterday:
        parts.append(f"Yesterday Summary: {yesterday}")
    tasks = context.get("todays_tasks")
    if tasks:
        parts.append(f"Today's Tasks ({len(tasks)}):")
        for t in tasks:
            parts.append(f"  - [{t.get('status', '?')}] {t.get('title', '?')} ({t.get('agent_type', '?')})")
    return "\n".join(parts)
