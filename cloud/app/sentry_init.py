"""Sentry error tracking initialization.

Safe to call with empty DSN — becomes a no-op. Logs init status so
misconfiguration is visible in Railway logs (don't fail silently).

PII protection:
- send_default_pii=False (no IPs, cookies, usernames)
- max_request_body_size="never" (no request bodies captured — Stripe
  webhooks contain customer emails and amounts)
- before_send scrubs Authorization/Cookie headers + known secret keys
"""
from __future__ import annotations

import logging
import os
from typing import Any

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.config import Settings

_log = logging.getLogger(__name__)

# Header/body keys to scrub even if they slip through
_SENSITIVE_HEADERS = {"authorization", "cookie", "x-api-key", "x-stripe-signature"}
_SENSITIVE_KEYS = {
    "password",
    "supabase_service_key",
    "supabase_anon_key",
    "stripe_webhook_secret",
    "stripe_secret_key",
    "access_token",
    "refresh_token",
    "api_key",
}


def _scrub_event(event: Any, _hint: Any) -> Any:
    """Strip sensitive headers and known secret keys from outbound events.

    Defense-in-depth: send_default_pii and max_request_body_size cover most
    cases, but headers still flow through — scrub them explicitly.

    Typed as Any because Sentry's Event is a complex TypedDict; we only
    touch dict-shaped fields defensively.
    """
    if not isinstance(event, dict):
        return event
    request = event.get("request")
    if isinstance(request, dict):
        headers = request.get("headers")
        if isinstance(headers, dict):
            for key in list(headers.keys()):
                if key.lower() in _SENSITIVE_HEADERS:
                    headers[key] = "[Filtered]"
        # Drop query string tokens (Supabase sometimes puts JWTs in URLs)
        query = request.get("query_string")
        if isinstance(query, str) and ("token=" in query.lower() or "access_token=" in query.lower()):
            request["query_string"] = "[Filtered]"

    # Scrub extras and contexts
    for section in ("extra", "contexts"):
        block = event.get(section)
        if isinstance(block, dict):
            _scrub_dict(block)

    return event


def _scrub_dict(d: dict[str, Any]) -> None:
    """Recursively replace values whose keys look sensitive."""
    for key, value in list(d.items()):
        if isinstance(key, str) and key.lower() in _SENSITIVE_KEYS:
            d[key] = "[Filtered]"
        elif isinstance(value, dict):
            _scrub_dict(value)


def _resolve_release(settings: Settings) -> str:
    """Prefer explicit setting, fall back to Railway SHA, then 'dev'."""
    if settings.sentry_release:
        return settings.sentry_release
    sha = os.environ.get("RAILWAY_GIT_COMMIT_SHA", "")
    if sha:
        return f"gradata-cloud@{sha[:7]}"
    return "gradata-cloud@dev"


def init_sentry(settings: Settings) -> None:
    """Initialize Sentry SDK. No-op when DSN is unset."""
    if not settings.sentry_dsn:
        _log.info("Sentry disabled: GRADATA_SENTRY_DSN not set")
        return

    release = _resolve_release(settings)
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        release=release,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
        # Never capture request bodies — Stripe webhooks contain customer data
        max_request_body_size="never",
        # Don't include local variables in stack frames (can leak secrets)
        include_local_variables=False,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            StarletteIntegration(transaction_style="endpoint"),
        ],
        before_send=_scrub_event,
    )
    _log.info(
        "Sentry initialized: environment=%s release=%s traces_sample_rate=%.2f",
        settings.environment,
        release,
        settings.sentry_traces_sample_rate,
    )
