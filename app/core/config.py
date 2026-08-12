from __future__ import annotations

from functools import lru_cache

from pydantic import Field, PostgresDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.enums import AIProviderType

# Known insecure default from this repository — rejected when app_env != "development".
DEFAULT_JWT_SECRET_KEY = "change-me-to-a-long-random-secret-in-production"
# Defense-in-depth length floor for non-development (Phase D Decision 10).
JWT_SECRET_MIN_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        hide_input_in_errors=True,
    )

    app_name: str = "Affiliate Platform API"
    app_env: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    host: str = "0.0.0.0"
    port: int = 8000

    postgres_user: str = "affiliate"
    postgres_password: str = "affiliate_secret"
    postgres_db: str = "affiliate_db"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    database_url: PostgresDsn | str = Field(
        default="postgresql+asyncpg://affiliate:affiliate_secret@localhost:5432/affiliate_db"
    )

    jwt_secret_key: str = DEFAULT_JWT_SECRET_KEY
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    cors_origins: list[str] = ["http://localhost:3000"]

    telegram_bot_token: str | None = None
    telegram_api_base_url: str = "https://api.telegram.org"

    ai_default_provider: AIProviderType = AIProviderType.OPENAI
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_api_base_url: str = "https://api.openai.com/v1"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"
    gemini_api_base_url: str = "https://generativelanguage.googleapis.com/v1beta"

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None
    celery_publish_interval_seconds: int = 60
    celery_publish_batch_size: int = 50

    aliexpress_app_key: str | None = None
    aliexpress_app_secret: str | None = None
    aliexpress_tracking_id: str | None = None
    aliexpress_api_url: str = "https://api-sg.aliexpress.com/sync"
    aliexpress_target_currency: str = "USD"
    aliexpress_target_language: str = "EN"
    aliexpress_country: str = "IL"
    aliexpress_request_timeout: float = 30.0
    aliexpress_max_retries: int = 3
    aliexpress_retry_backoff_seconds: float = 0.5
    aliexpress_rate_limit_interval_seconds: float = 0.2
    aliexpress_smartmatch_device_id: str = "affiliate-platform-discovery"
    aliexpress_enable_ds_image_search: bool = False
    aliexpress_discovery_refresh_batch_size: int = 50
    aliexpress_discovery_refresh_max_pages: int = 2
    celery_discovery_hot_interval_seconds: int = 21600
    celery_discovery_trending_interval_seconds: int = 21600
    celery_discovery_categories_interval_seconds: int = 86400
    # Phase B Task 1 — Beat→worker pipeline heartbeat (Redis TTL key).
    # TTL defaults to 3× interval so one missed tick does not flap health.
    celery_heartbeat_interval_seconds: int = 30
    celery_heartbeat_ttl_seconds: int = 90

    @property
    def broker_url(self) -> str:
        if self.celery_broker_url:
            return self.celery_broker_url
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def result_backend_url(self) -> str:
        if self.celery_result_backend:
            return self.celery_result_backend
        return self.broker_url

    @field_validator("database_url", mode="before")
    @classmethod
    def assemble_db_connection(cls, value: str | None, info) -> str:
        if value:
            return str(value)
        data = info.data
        return (
            f"postgresql+asyncpg://{data.get('postgres_user')}:"
            f"{data.get('postgres_password')}@{data.get('postgres_host')}:"
            f"{data.get('postgres_port')}/{data.get('postgres_db')}"
        )

    @model_validator(mode="after")
    def validate_jwt_secret_for_environment(self) -> Settings:
        # Development retains the existing developer/default-secret workflow.
        if self.is_development:
            return self

        if self.jwt_secret_key == DEFAULT_JWT_SECRET_KEY:
            raise ValueError(
                "JWT_SECRET_KEY must not use the repository default secret "
                f"when app_env is '{self.app_env}'"
            )
        if len(self.jwt_secret_key) < JWT_SECRET_MIN_LENGTH:
            raise ValueError(
                "JWT_SECRET_KEY must be at least "
                f"{JWT_SECRET_MIN_LENGTH} characters when app_env is '{self.app_env}'"
            )
        return self

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
