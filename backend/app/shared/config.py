from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, validated at startup so a missing variable fails fast."""

    model_config = SettingsConfigDict(
        # Native runs start in backend/, so the shared .env lives one level up.
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "academia-backend"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://academia:academia@localhost:5432/academia"
    chroma_url: str = "http://localhost:8001"
    cors_origins: list[str] = ["http://localhost:3000"]
    health_check_timeout_seconds: float = 2.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
