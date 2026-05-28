"""Company config API routes — GET/PUT company configuration."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import verify_api_key
from app.core.database import get_db
from app.models.company_config import CompanyConfig

router = APIRouter(tags=["config"])


def _config_to_dict(config: CompanyConfig) -> dict[str, Any]:
    """Serialize company config to dict."""
    return {
        "id": config.id,
        "name": config.name,
        "mission": config.mission,
        "vision": config.vision,
        "description": config.description,
        "target_market": config.target_market,
        "value_prop": config.value_prop,
        "pricing_model": config.pricing_model,
        "goals": config.goals,
        "kpis": config.kpis,
        "website_url": config.website_url,
        "github_repo": config.github_repo,
        "product_type": config.product_type,
        "industry": config.industry,
        "timezone": config.timezone,
        "daily_cycle_hour": config.daily_cycle_hour,
    }


@router.get("/config")
async def get_config(
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Get the company configuration."""
    result = await db.execute(select(CompanyConfig).limit(1))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="No company config found")
    return _config_to_dict(config)


@router.put("/config")
async def update_config(
    body: dict[str, Any],
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Update company configuration. Creates if not exists."""
    result = await db.execute(select(CompanyConfig).limit(1))
    config = result.scalar_one_or_none()
    if not config:
        config = CompanyConfig(name=body.get("name", "New Company"))
        db.add(config)
        await db.flush()

    for key, value in body.items():
        if hasattr(config, key) and value is not None:
            setattr(config, key, value)
    await db.flush()
    return _config_to_dict(config)
