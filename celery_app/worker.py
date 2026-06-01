from celery import Celery

app = Celery("polsia")
app.config_from_object("celery_app.celery_config")

# Explicit imports so Celery can register shared_task decorators
from celery_app.tasks import agent_tasks  # noqa: F401
from celery_app.tasks import daily_cycle  # noqa: F401
