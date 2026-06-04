"""Application configuration via Pydantic Settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    app_name: str = "Polsia Fork"
    debug: bool = True
    api_key: str = "dev-key"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/polsia"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/1"

    # LLM API (replaces original Claude Code CLI subprocess)
    llm_api_mock: bool = True
    llm_api_key: str = ""
    llm_api_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"
    llm_mock_response: str = '{"result": "Mock LLM response for testing"}'

    # ModelInstance (Phase 3) — optional usage tracking
    model_usage_log_enabled: bool = False
    """When ``True``, persist ModelCall usage records to the database."""

    model_rate_limit_rpm: int = 60
    """Default requests-per-minute limit per ModelInstance."""

    model_rate_limit_tpm: int = 100_000
    """Default tokens-per-minute limit per ModelInstance."""

    # ChromaDB
    chroma_db_path: str = "./chroma_db"

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_lookup: dict = {
        "basic": "",       # price_xxx for ¥2K
        "standard": "",    # price_xxx for ¥3K  
        "enterprise": "",  # price_xxx for ¥5K
    }

    # Base URL for frontend links in emails
    base_url: str = "http://127.0.0.1:9999"

    # Email / SMTP
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "noreply@crosswave.app"
    smtp_from_name: str = "CrossWave"

    # Schedules (hour of day)
    morning_cycle_hour: int = 6
    evening_cycle_hour: int = 18

    # Durable execution (checkpoint)
    durable_execution_enabled: bool = False
    """Opt-in: when True, Celery tasks use checkpoint-based durable execution."""

    # Multi-tenant
    default_plan: str = "starter"
    default_agents_limit: int = 3
    default_tasks_monthly_limit: int = 1000
    default_tokens_monthly_limit: int = 10_000_000

    # Quota system
    quota_enabled: bool = True
    """Master switch for quota enforcement. When ``False`` all checks pass."""

    quota_middleware_enabled: bool = True
    """Master switch for the quota enforcement middleware. When ``False``
    the middleware skips all checks and passes requests through."""
    """Master switch for quota enforcement.  When ``False`` all checks pass."""

    # Sandbox runtime (Docker container isolation)
    sandbox_enabled: bool = False
    """When ``True``, route agent execution through Docker sandbox containers."""

    # Resource-aware agent scheduler
    scheduler_enabled: bool = True
    """When ``True``, the scheduler gates agent dispatch through load-aware
    queue assignment. When ``False``, agents go directly to the default queue."""

    quota_warning_threshold: float = 0.8
    """Usage percentage at which warnings are issued (0.0 – 1.0)."""

    model_config = {"env_prefix": ""}


settings = Settings()
