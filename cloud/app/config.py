"""Settings from environment variables."""
from __future__ import annotations

from functools import lru_cache

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

    # Sentry (all optional — empty DSN = disabled)
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.1
    sentry_release: str = ""  # Falls back to RAILWAY_GIT_COMMIT_SHA, then "dev"

    # Stripe (all optional — empty values mean "not configured")
    # Env vars: GRADATA_STRIPE_SECRET_KEY, GRADATA_STRIPE_WEBHOOK_SECRET,
    # GRADATA_STRIPE_PRICE_ID_CLOUD, GRADATA_STRIPE_PRICE_ID_TEAM
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id_cloud: str = ""
    stripe_price_id_team: str = ""
    stripe_success_url: str = "https://app.gradata.ai/billing?success=1"
    stripe_cancel_url: str = "https://app.gradata.ai/billing?cancel=1"
    stripe_portal_return_url: str = "https://app.gradata.ai/billing"

    model_config = {"env_prefix": "GRADATA_", "env_file": ".env", "extra": "ignore"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings loader."""
    return Settings()  # type: ignore[call-arg]
