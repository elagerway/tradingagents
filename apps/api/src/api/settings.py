"""Runtime configuration via environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Supabase
    supabase_url: str = Field(..., description="https://<ref>.supabase.co")
    supabase_service_role_key: str = Field(..., description="Service role key (secret)")
    supabase_jwt_secret: str = Field("", description="HS256 secret if project uses legacy auth")

    # CORS — comma-separated origins for the web app.
    cors_origins: str = Field(
        "http://localhost:3000",
        description="Comma-separated list of allowed origins for CORS",
    )

    # Engine
    use_fake_engine: bool = Field(True, description="Plan 2 ships with fake; Plan 4 flips this")

    # Janitor
    stuck_run_threshold_minutes: int = Field(
        30, description="Mark running rows older than this as failed"
    )

    # Logging
    log_level: str = Field("INFO")
    log_json: bool = Field(True, description="Emit JSON logs (off in local dev for readability)")


@lru_cache
def get_settings() -> Settings:
    return Settings()
