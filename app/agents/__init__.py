"""AI Agents — 10 specialized agents for autonomous company operation."""

from app.agents.base import BasePolsiaAgent, agent_map, register_agent

# Import all agent modules so @register_agent decorators fire
from app.agents import (  # noqa: F401
    ads_management,
    business_planning,
    code_generation,
    competitor_research,
    customer_support,
    deployment,
    email_outreach,
    finance,
    orchestrator,
    social_media,
)
