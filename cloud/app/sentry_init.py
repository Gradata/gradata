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
    # PII — opaque user.id is fine (set via set_user), but raw email never
    # belongs in event extras/contexts. Scrub defensively even though
    # send_default_pii=False covers the default integrations.
    "email",
    "email_address",
    "user_email",
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

    # Scrub extras and contexts — Sentry sometimes nests lists of dicts here
    # (e.g. breadcrumb-like items under contexts), so the scrubber must walk
    # list/tuple containers as well as dicts.
    for section in ("extra", "contexts"):
        block = event.get(section)
        if block is not None:
            event[section] = _scrub_value(block)

    return event


def _scrub_value(value: Any) -> Any:
    """Recursively scrub sensitive keys inside dicts / lists / tuples.

    - dict: replace values whose keys match _SENSITIVE_KEYS (case-insensitive)
      with "[Filtered]"; recurse into other values in-place.
    - list: recurse into each element in-place.
    - tuple: return a new tuple with each element scrubbed (tuples are immutable).
    - other: return as-is.
    """
    if isinstance(value, dict):
        for key, child in list(value.items()):
            if isinstance(key, str) and key.lower() in _SENSITIVE_KEYS:
                value[key] = "[Filtered]"
            else:
                value[key] = _scrub_value(child)
        return value
    if isinstance(value, list):
        for i, child in enumerate(value):
            value[i] = _scrub_value(child)
        return value
    if isinstance(value, tuple):
        return tuple(_scrub_value(child) for child in value)
    return value


# Kept for backwards compatibility with any external callers. New code should
# use `_scrub_value` which handles list/tuple containers too.
def _scrub_dict(d: dict[str, Any]) -> None:
    """Recursively replace values whose keys look sensitive (in-place)."""
    _scrub_value(d)


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
        profiles_sample_rate=settings.sentry_profiles_sample_rate,
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
        "Sentry initialized: environment=%s release=%s "
        "traces_sample_rate=%.2f profiles_sample_rate=%.2f",
        settings.environment,
        release,
        settings.sentry_traces_sample_rate,
        settings.sentry_profiles_sample_rate,
    )


def tag_user(user_id: str, workspace_id: str | None = None) -> None:
    """Attach user.id + workspace_id to the current Sentry scope.

    No-op when Sentry isn't initialised. Call from auth dependencies
    (get_current_user_id, get_current_brain, require_operator) so any
    exception raised downstream already carries the request's owner.
    """
    client = sentry_sdk.get_client()
    if client is None or not client.is_active():
        return
    # Use the isolation scope so the tag lives for the whole request,
    # not just the current task. Both FastAPI and Starlette integrations
    # push an isolation scope per request.
    scope = sentry_sdk.get_isolation_scope()
    # `set_user` only sends the opaque UUID — no email/username — which
    # matches our GDPR-minimal stance (send_default_pii=False).
    scope.set_user({"id": user_id})
    if workspace_id:
        scope.set_tag("workspace_id", workspace_id)
