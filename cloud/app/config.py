"""Settings from environment variables."""
from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All config comes from env vars. No defaults for secrets."""

    # Supabase
    supabase_url: str         # e.g. https://xxxx.supabase.co
    supabase_anon_key: str    # from Supabase dashboard
    supabase_service_key: str # service role key for server-side RLS bypass
    supabase_jwt_key: str     # for verifying user JWTs

    # App
    environment: str = "development"
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:3000", "https://app.gradata.ai"]

    model_config = {"env_prefix": "GRADATA_", "env_file": ".env", "extra": "ignore"}


def get_settings() -> Settings:
    """Cached settings loader."""
    return Settings()  # type: ignore[call-arg]
