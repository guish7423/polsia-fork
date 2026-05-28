"""AI Agents — 10 specialized agents for autonomous company operation."""


# Import all agent modules to trigger @register_agent decorators
import app.agents.orchestrator  # noqa: F401
import app.agents.business_planning  # noqa: F401
import app.agents.competitor_research  # noqa: F401
import app.agents.social_media  # noqa: F401
import app.agents.email_outreach  # noqa: F401
import app.agents.customer_support  # noqa: F401
import app.agents.ads_management  # noqa: F401
import app.agents.code_generation  # noqa: F401
import app.agents.finance  # noqa: F401
import app.agents.deployment  # noqa: F401
from app.agents.base import BasePolsiaAgent, agent_map, register_agent
