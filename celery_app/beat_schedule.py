from celery.schedules import crontab

from app.config import settings

beat_schedule = {
    # Morning orchestration cycle
    "morning-cycle": {
        "task": "celery_app.tasks.daily_cycle.run_morning_cycle",
        "schedule": crontab(hour=settings.morning_cycle_hour, minute=0),
        "options": {"queue": "scheduler"},
    },
    # Evening reporting cycle
    "evening-cycle": {
        "task": "celery_app.tasks.daily_cycle.run_evening_cycle",
        "schedule": crontab(hour=settings.evening_cycle_hour, minute=0),
        "options": {"queue": "scheduler"},
    },
    # Every 2h: check social mentions
    "social-mentions-sweep": {
        "task": "celery_app.tasks.agent_tasks.run_social_sweep",
        "schedule": crontab(minute=0, hour="*/2"),
        "options": {"queue": "agents"},
    },
    # Every 3h: check email inbox
    "email-inbox-sweep": {
        "task": "celery_app.tasks.agent_tasks.run_email_sweep",
        "schedule": crontab(minute=30, hour="*/3"),
        "options": {"queue": "agents"},
    },
    # Every 4h: deploy agent sweep
    "deploy-sweep": {
        "task": "celery_app.tasks.agent_tasks.run_deploy_sweep",
        "schedule": crontab(minute=30, hour="*/4"),
        "options": {"queue": "agents"},
    },
    # Every 4h: scan external platforms for new orders
    "order-scan-sweep": {
        "task": "celery_app.tasks.agent_tasks.run_order_scan",
        "schedule": crontab(minute=0, hour="*/4"),
        "options": {"queue": "agents"},
    },
    # Every 2h: fulfill accepted orders
    "order-fulfill-sweep": {
        "task": "celery_app.tasks.agent_tasks.run_order_fulfill",
        "schedule": crontab(minute=30, hour="*/2"),
        "options": {"queue": "agents"},
    },
    # Every 1h: nurture new leads
    "lead-nurture-sweep": {
        "task": "celery_app.tasks.agent_tasks.run_lead_nurture",
        "schedule": crontab(minute=15, hour="*"),
        "options": {"queue": "agents"},
    },
    # Every 5min: monitor all services health
    "monitor-sweep": {
        "task": "celery_app.tasks.agent_tasks.run_monitor_sweep",
        "schedule": crontab(minute="*/5"),
        "options": {"queue": "agents"},
    },
    # Every 6h: sync ad metrics + Stripe failed payments
    "ads-stripe-sync": {
        "task": "celery_app.tasks.agent_tasks.run_ads_stripe_sync",
        "schedule": crontab(minute=0, hour="*/6"),
        "options": {"queue": "agents"},
    },
    # Daily at 23:00: evolution analysis — review agent performance
    "evolution-sweep": {
        "task": "celery_app.tasks.agent_tasks.run_evolution_sweep",
        "schedule": crontab(hour=23, minute=0),
        "options": {"queue": "agents"},
    },
    # Daily at 7:00: market intelligence briefing — scan web for news/competitors/opportunities
    "briefing-sweep": {
        "task": "celery_app.tasks.agent_tasks.run_briefing_sweep",
        "schedule": crontab(hour=7, minute=0),
        "options": {"queue": "agents"},
    },
    # Daily at 3:00: sandbox cleanup — expire pending actions older than 72h
    "sandbox-cleanup": {
        "task": "celery_app.tasks.agent_tasks.run_sandbox_cleanup",
        "schedule": crontab(hour=3, minute=0),
        "options": {"queue": "maintenance"},
    },
    # Daily at 10:00: proposal nurture — check for sent-but-unread proposals needing follow-up
    "proposal-nurture-sweep": {
        "task": "celery_app.tasks.agent_tasks.run_proposal_nurture_sweep",
        "schedule": crontab(hour=10, minute=0),
        "options": {"queue": "agents"},
    },
}
