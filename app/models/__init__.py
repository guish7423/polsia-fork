"""Models package - all models imported for Alembic discovery."""

from app.models.base import Base, TimestampMixin
from app.models.company_config import CompanyConfig
from app.models.task import Task
from app.models.agent_run import AgentRun
from app.models.activity_log import ActivityLog
from app.models.memory_entry import MemoryEntry
from app.models.social import SocialPost, SocialEngagement
from app.models.email import Prospect, EmailCampaign, EmailLog
from app.models.ad import AdCampaign, AdMetric
from app.models.competitor import Competitor
from app.models.stripe import StripeEvent
from app.models.finance import RevenueSnapshot, ExpenseRecord
from app.models.report import DailyReport

__all__ = [
    "Base",
    "TimestampMixin",
    "CompanyConfig",
    "Task",
    "AgentRun",
    "ActivityLog",
    "MemoryEntry",
    "SocialPost",
    "SocialEngagement",
    "Prospect",
    "EmailCampaign",
    "EmailLog",
    "AdCampaign",
    "AdMetric",
    "Competitor",
    "StripeEvent",
    "RevenueSnapshot",
    "ExpenseRecord",
    "DailyReport",
]
