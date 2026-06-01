"""Celery application for Polsia Fork."""

from celery import Celery

app = Celery("polsia")
app.config_from_object("celery_app.celery_config")

# Explicit task imports — autodiscover_tasks can't find modules in packages
from celery_app.tasks import agent_tasks, daily_cycle, maintenance  # noqa: F401
