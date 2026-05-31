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
