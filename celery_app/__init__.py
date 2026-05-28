"""Celery application for Polsia Fork (lazy init — allows tests without celery)."""
try:
    from celery import Celery
    app = Celery("polsia")
    app.config_from_object("celery_app.celery_config")
    app.autodiscover_tasks(["celery_app.tasks"])
except ImportError:
    app = None  # Celery not installed — tasks run inline or via mocks

# Ensure tasks submodule is importable for test patches
from celery_app import tasks  # noqa: F401, E402
