"""Tests for Sentry initialization and PII scrubbing."""

from __future__ import annotations

import logging

import sentry_sdk

from app.config import Settings
from app.sentry_init import _resolve_release, _scrub_event, init_sentry


def _make_settings(**overrides) -> Settings:
    """Build Settings with test defaults + overrides."""
    base = dict(
        supabase_url="https://test.supabase.co",
        supabase_anon_key="TVAL",
        supabase_service_key="TVAL",
        supabase_jwt_key="test-only-hmac-not-a-real-credential-x",
        environment="test",
        sentry_dsn="",
    )
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def test_init_sentry_noop_when_dsn_empty(caplog):
    """Empty DSN must not raise and must log it's disabled (visible misconfig)."""
    settings = _make_settings(sentry_dsn="")
    with caplog.at_level(logging.INFO, logger="app.sentry_init"):
        init_sentry(settings)
    assert any("disabled" in rec.message.lower() for rec in caplog.records)


def test_init_sentry_enabled_when_dsn_set(caplog):
    """Valid DSN must init Sentry and log success (visible misconfig)."""
    # Use an obviously-fake DSN that Sentry SDK accepts syntactically
    fake_dsn = "https://publickey@o0.ingest.sentry.io/0"
    settings = _make_settings(sentry_dsn=fake_dsn, environment="test")
    with caplog.at_level(logging.INFO, logger="app.sentry_init"):
        init_sentry(settings)
    # Client should exist after init (use 2.x API, not deprecated Hub)
    client = sentry_sdk.get_client()
    assert client is not None and client.is_active(), "Sentry SDK client not active"
    assert any("initialized" in rec.message.lower() for rec in caplog.records)


def test_scrub_event_removes_authorization_header():
    event = {"request": {"headers": {"Authorization": "Bearer secret123", "User-Agent": "ua"}}}
    scrubbed = _scrub_event(event, {})
    assert scrubbed["request"]["headers"]["Authorization"] == "[Filtered]"
    assert scrubbed["request"]["headers"]["User-Agent"] == "ua"


def test_scrub_event_removes_cookie_and_stripe_signature():
    event = {
        "request": {
            "headers": {
                "Cookie": "session=abc",
                "X-Stripe-Signature": "sig",
                "X-API-Key": "key",
            }
        }
    }
    scrubbed = _scrub_event(event, {})
    headers = scrubbed["request"]["headers"]
    assert headers["Cookie"] == "[Filtered]"
    assert headers["X-Stripe-Signature"] == "[Filtered]"
    assert headers["X-API-Key"] == "[Filtered]"


def test_scrub_event_strips_token_query_string():
    event = {"request": {"query_string": "foo=bar&access_token=abc"}}
    scrubbed = _scrub_event(event, {})
    assert scrubbed["request"]["query_string"] == "[Filtered]"


def test_scrub_event_scrubs_sensitive_keys_in_extra():
    event = {
        "extra": {
            "supabase_service_key": "real-secret",
            "stripe_webhook_secret": "whsec_xyz",
            "safe_field": "keep",
        }
    }
    scrubbed = _scrub_event(event, {})
    assert scrubbed["extra"]["supabase_service_key"] == "[Filtered]"
    assert scrubbed["extra"]["stripe_webhook_secret"] == "[Filtered]"
    assert scrubbed["extra"]["safe_field"] == "keep"


def test_scrub_event_handles_non_dict_input():
    """Never crash on unexpected event shapes."""
    assert _scrub_event(None, {}) is None
    assert _scrub_event("string", {}) == "string"


def test_resolve_release_uses_explicit_setting():
    settings = _make_settings(sentry_release="v1.2.3")
    assert _resolve_release(settings) == "v1.2.3"


def test_resolve_release_falls_back_to_railway_sha(monkeypatch):
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "abc1234def5678")
    settings = _make_settings(sentry_release="")
    release = _resolve_release(settings)
    assert release == "gradata-cloud@abc1234"


def test_resolve_release_falls_back_to_dev(monkeypatch):
    monkeypatch.delenv("RAILWAY_GIT_COMMIT_SHA", raising=False)
    settings = _make_settings(sentry_release="")
    assert _resolve_release(settings) == "gradata-cloud@dev"


def test_scrub_event_scrubs_email_fields():
    """PII: email keys under extras/contexts must be [Filtered]."""
    event = {
        "extra": {"email": "oliver@sprites.ai", "user_email": "x@y.z"},
        "contexts": {"user_ctx": {"email_address": "a@b.c", "ok": 1}},
    }
    scrubbed = _scrub_event(event, {})
    assert scrubbed["extra"]["email"] == "[Filtered]"
    assert scrubbed["extra"]["user_email"] == "[Filtered]"
    assert scrubbed["contexts"]["user_ctx"]["email_address"] == "[Filtered]"
    assert scrubbed["contexts"]["user_ctx"]["ok"] == 1


def test_init_sentry_passes_profiles_sample_rate(monkeypatch):
    """Verify profiles_sample_rate is forwarded to sentry_sdk.init."""
    captured = {}

    def _fake_init(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(sentry_sdk, "init", _fake_init)
    settings = _make_settings(
        sentry_dsn="https://publickey@o0.ingest.sentry.io/0",
        sentry_traces_sample_rate=0.1,
        sentry_profiles_sample_rate=0.1,
    )
    init_sentry(settings)
    assert captured["traces_sample_rate"] == 0.1
    assert captured["profiles_sample_rate"] == 0.1


def test_tag_user_sets_scope_user_and_workspace_tag():
    """tag_user() must attach user.id + workspace_id to the current scope."""
    from app.sentry_init import init_sentry, tag_user

    settings = _make_settings(sentry_dsn="https://publickey@o0.ingest.sentry.io/0")
    init_sentry(settings)

    with sentry_sdk.isolation_scope() as iso_scope:
        tag_user("user-abc-123", workspace_id="ws-xyz-9")
        # tag_user writes to the isolation scope; read it back the same way.
        data = iso_scope.to_dict() if hasattr(iso_scope, "to_dict") else {}
        user = data.get("user") or getattr(iso_scope, "_user", None)
        tags = data.get("tags") or dict(getattr(iso_scope, "_tags", {}) or {})
        assert user and user.get("id") == "user-abc-123", f"user not tagged: {data}"
        assert tags.get("workspace_id") == "ws-xyz-9", f"workspace not tagged: {data}"


def test_tag_user_noop_when_sentry_disabled(monkeypatch):
    """With DSN unset, tag_user must be a safe no-op (no raise)."""
    # Close any active Sentry client from prior tests so get_client().is_active() == False.
    client = sentry_sdk.get_client()
    if client is not None:
        client.close()

    from app.sentry_init import tag_user
    # Must not raise even when Sentry isn't configured.
    tag_user("user-1", workspace_id="ws-1")


def test_app_creates_cleanly_without_sentry_dsn(monkeypatch):
    """Regression: create_app() must not raise when Sentry is disabled."""
    monkeypatch.delenv("GRADATA_SENTRY_DSN", raising=False)
    # Clear settings cache so new env is picked up
    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import create_app

    app = create_app()
    assert app is not None
    assert app.title == "Gradata Cloud API"
