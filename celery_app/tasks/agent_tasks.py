"""Celery tasks for dispatching agents."""
from app.agents.crew_factory import run_agent_for_task_sync

try:
    from celery import shared_task
except ImportError:
    # Celery not available — stub for test compatibility
    def shared_task(*args, **kwargs):
        def decorator(f):
            f.delay = lambda *a, **kw: None
            return f
        return decorator(args[0]) if args and callable(args[0]) else decorator


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def run_agent(self, agent_type: str, context: dict | None = None) -> dict:
    """Run any registered agent by type. Generic dispatcher for Celery Beat."""
    try:
        return run_agent_for_task_sync(agent_type, context or {})
    except ValueError:
        raise
    except Exception as exc:
        self.retry(exc=exc)


run_agent_task = run_agent  # Alias for test compatibility
