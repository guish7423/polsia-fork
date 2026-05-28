"""Authentication and registration routes — multi-tenant signup."""
import secrets
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.subscription import Subscription
from app.schemas.auth import SignupRequest, SignupResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=SignupResponse)
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)):
    """Register a new company and get API key."""
    # Check email uniqueness
    result = await db.execute(
        select(Subscription).where(Subscription.email == body.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    api_key = secrets.token_hex(16)
    sub = Subscription(
        email=body.email,
        api_key=api_key,
        plan="starter",
        status="trialing",
        active=True,
        agents_limit=3,
        tasks_monthly_limit=1000,
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)

    return SignupResponse(
        api_key=api_key,
        company_id=sub.id,
        plan=sub.plan,
        trial_days=14,
    )
