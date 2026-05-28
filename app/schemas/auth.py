"""Pydantic schemas for auth and registration."""
from pydantic import BaseModel



class SignupRequest(BaseModel):
    email: str
    company_name: str = "My Company"


class SignupResponse(BaseModel):
    api_key: str
    company_id: int
    plan: str
    trial_days: int
