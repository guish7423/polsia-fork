"""API key authentication — validates key and resolves company context."""
from fastapi import Header, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db
from app.models.subscription import Subscription


async def verify_api_key(
    x_api_key: str = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> str:
    """Validate API key. Checks global admin key first, then Subscription table."""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    # Admin key (backward compat for tests / admin)
    if x_api_key == settings.api_key:
        return x_api_key

    # Per-tenant key from Subscription table
    result = await db.execute(
        select(Subscription).where(Subscription.api_key == x_api_key)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid API key")
    if not sub.active and sub.status not in ("trialing", "active"):
        raise HTTPException(status_code=403, detail="Subscription inactive")

    return x_api_key


async def get_current_company(
    x_api_key: str = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> tuple[int, Subscription]:
    """Resolve company_id and Subscription from API key."""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    # Admin key returns a generic company context
    if x_api_key == settings.api_key:
        return 0, None

    result = await db.execute(
        select(Subscription).where(Subscription.api_key == x_api_key)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return sub.id, sub
