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

    # ChromaDB
    chroma_db_path: str = "./chroma_db"

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

    model_config = {"env_prefix": ""}


settings = Settings()
