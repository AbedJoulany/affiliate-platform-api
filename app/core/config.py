from functools import lru_cache

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
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

    jwt_secret_key: str = "change-me-to-a-long-random-secret-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    cors_origins: list[str] = ["http://localhost:3000"]

    telegram_bot_token: str | None = None
    telegram_api_base_url: str = "https://api.telegram.org"

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

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
