"""Authentication and registration routes — multi-tenant signup + onboarding."""
import secrets
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_company
from app.core.database import get_db
from app.models.subscription import Subscription
from app.schemas.auth import SignupRequest, SignupResponse, MeResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=SignupResponse)
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)):
    """Register a new company and get API key."""
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
        onboarding_completed=False,
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


@router.get("/me", response_model=MeResponse)
async def get_me(
    db: AsyncSession = Depends(get_db),
    current: tuple[int, Subscription | None] = Depends(get_current_company),
):
    """Return current subscription info."""
    _, sub = current
    if not sub:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return MeResponse(
        email=sub.email,
        api_key=sub.api_key,
        plan=sub.plan,
        status=sub.status,
        active=sub.active,
        agents_limit=sub.agents_limit,
        tasks_monthly_limit=sub.tasks_monthly_limit,
        onboarding_completed=sub.onboarding_completed,
        current_period_end=(
            sub.current_period_end.isoformat() if sub.current_period_end else None
        ),
    )


@router.post("/onboarding/complete")
async def complete_onboarding(
    db: AsyncSession = Depends(get_db),
    current: tuple[int, Subscription | None] = Depends(get_current_company),
):
    """Mark onboarding as completed."""
    sub_id, sub = current
    if not sub:
        raise HTTPException(status_code=401, detail="Not authenticated")

    sub.onboarding_completed = True
    await db.commit()
    return {"ok": True}
