"""Pydantic schemas for auth, registration, and onboarding."""
from pydantic import BaseModel, EmailStr


class SignupRequest(BaseModel):
    email: EmailStr
    company_name: str = "My Company"


class SignupResponse(BaseModel):
    api_key: str
    company_id: int
    plan: str
    trial_days: int = 14


class MeResponse(BaseModel):
    email: str
    api_key: str
    plan: str
    status: str
    active: bool
    agents_limit: int
    tasks_monthly_limit: int
    onboarding_completed: bool
    current_period_end: str | None = None
