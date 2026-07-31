"""Centralized configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All VVF services share this settings model.

    Every container reads the same ``.env``; unused vars are simply ignored.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="VVF_", extra="ignore", case_sensitive=False
    )

    env: str = "development"
    log_level: str = "INFO"
    secret_key: str = "change-me-to-a-long-random-string"

    # Auth
    admin_username: str = "admin"
    admin_password: str = "changeme"

    # Database / redis (accept both VVF_-prefixed and unprefixed env vars)
    postgres_host: str = Field(
        default="localhost", validation_alias=AliasChoices("VVF_POSTGRES_HOST", "POSTGRES_HOST")
    )
    postgres_port: int = Field(
        default=5432, validation_alias=AliasChoices("VVF_POSTGRES_PORT", "POSTGRES_PORT")
    )
    postgres_db: str = Field(
        default="vvf", validation_alias=AliasChoices("VVF_POSTGRES_DB", "POSTGRES_DB")
    )
    postgres_user: str = Field(
        default="vvf", validation_alias=AliasChoices("VVF_POSTGRES_USER", "POSTGRES_USER")
    )
    postgres_password: str = Field(
        default="", validation_alias=AliasChoices("VVF_POSTGRES_PASSWORD", "POSTGRES_PASSWORD")
    )

    redis_host: str = Field(
        default="localhost", validation_alias=AliasChoices("VVF_REDIS_HOST", "REDIS_HOST")
    )
    redis_port: int = Field(
        default=6379, validation_alias=AliasChoices("VVF_REDIS_PORT", "REDIS_PORT")
    )
    redis_password: str = Field(
        default="", validation_alias=AliasChoices("VVF_REDIS_PASSWORD", "REDIS_PASSWORD")
    )
    redis_db: int = Field(
        default=0, validation_alias=AliasChoices("VVF_REDIS_DB", "REDIS_DB")
    )

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000"
    # Public base URL the dashboard/agent use to reach this API (for artifact URLs).
    public_api_url: str = "http://localhost:8000"

    # Integrations
    # wigolo `serve` REST API (POST /v1/{tool}); token required off loopback.
    wigolo_base_url: str = "http://wigolo:3333"
    wigolo_api_token: str = ""
    wigolo_use_mock: bool = True
    # Discovery search tuning (see integrations/wigolo).
    wigolo_category: str = "news"
    wigolo_time_range: str = "week"
    wigolo_search_depth: str = "balanced"
    mpt_base_url: str = "http://127.0.0.1:8080"
    mpt_api_token: str = ""

    # LLM
    llm_provider: str = "openai"
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def database_dsn(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
