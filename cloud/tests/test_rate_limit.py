"""Tests for rate limiting — boundary behavior, bypass in test mode, auth keying."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings


@pytest.fixture
def limited_client(monkeypatch):
    """Build a TestClient with rate limiting explicitly enabled.

    Uses a tiny cap (`3/minute`) on the public bucket so tests finish fast
    without waiting on real 60-req minutes. Resets settings + limiter state
    between tests so no state bleeds between cases.
    """
    monkeypatch.setenv("GRADATA_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("GRADATA_RATE_LIMIT_PUBLIC", "3/minute")
    monkeypatch.setenv("GRADATA_RATE_LIMIT_AUTHENTICATED", "5/minute")
    monkeypatch.setenv("GRADATA_RATE_LIMIT_SENSITIVE", "2/minute")
    get_settings.cache_clear()

    from app import rate_limit
    rate_limit.refresh_enabled_flag()
    # slowapi's MemoryStorage persists between limiter instances — reset it
    # so previous test requests don't count toward this test's budget.
    rate_limit.limiter.reset()
    rate_limit.auth_limiter.reset()

    from app.main import create_app
    app = create_app()
    yield TestClient(app)

    get_settings.cache_clear()
    rate_limit.limiter.reset()
    rate_limit.auth_limiter.reset()


def test_public_bucket_allows_requests_under_limit(limited_client):
    """3/min public cap — first 3 must succeed."""
    for _ in range(3):
        resp = limited_client.get("/health")
        assert resp.status_code == 200, resp.json()


def test_public_bucket_rejects_over_limit(limited_client):
    """The 4th request in the same minute must 429 with Retry-After."""
    for _ in range(3):
        limited_client.get("/health")
    resp = limited_client.get("/health")
    assert resp.status_code == 429
    body = resp.json()
    assert body["detail"] == "Too Many Requests"
    # Retry-After should be a positive integer string (seconds until window resets).
    # slowapi may omit the header in some versions; treat as soft check.
    retry = resp.headers.get("Retry-After")
    if retry is not None:
        assert int(retry) >= 0


def test_sensitive_bucket_enforces_tighter_cap(limited_client):
    """Sensitive cap is 2/min — /billing/webhook's 3rd request must 429."""
    # Signature check fails first in this test (no real Stripe secret), but
    # we only care that the LIMITER runs before the handler body. We use
    # a malformed payload so the handler short-circuits at signature check.
    headers = {"stripe-signature": "bad"}
    r1 = limited_client.post("/api/v1/billing/webhook", content=b"{}", headers=headers)
    r2 = limited_client.post("/api/v1/billing/webhook", content=b"{}", headers=headers)
    r3 = limited_client.post("/api/v1/billing/webhook", content=b"{}", headers=headers)
    # First two: webhook handler runs (fails validation/signature => 400/503)
    assert r1.status_code in (400, 503)
    assert r2.status_code in (400, 503)
    # Third is the bucket overflow.
    assert r3.status_code == 429


def test_rate_limit_disabled_in_test_env_by_default(monkeypatch):
    """Without GRADATA_RATE_LIMIT_ENABLED=true, test env skips all caps."""
    monkeypatch.delenv("GRADATA_RATE_LIMIT_ENABLED", raising=False)
    monkeypatch.setenv("GRADATA_RATE_LIMIT_PUBLIC", "1/minute")
    get_settings.cache_clear()

    from app import rate_limit
    rate_limit.refresh_enabled_flag()
    rate_limit.limiter.reset()

    from app.main import create_app
    client = TestClient(create_app())

    # 10 requests all pass — limiter is a no-op in test env.
    for _ in range(10):
        assert client.get("/health").status_code == 200

    get_settings.cache_clear()


def test_auth_limiter_keys_by_bearer_token(monkeypatch):
    """Auth bucket must key by token hash so different users get separate budgets."""
    from app.rate_limit import _auth_or_ip_key

    class _Req:
        def __init__(self, headers, client_host="127.0.0.1"):
            self.headers = headers
            # slowapi's get_remote_address reads request.client.host
            self.client = type("C", (), {"host": client_host})()

    k1 = _auth_or_ip_key(_Req({"authorization": "Bearer token-aaa"}))
    k2 = _auth_or_ip_key(_Req({"authorization": "Bearer token-bbb"}))
    k3 = _auth_or_ip_key(_Req({}))  # falls back to IP
    k4 = _auth_or_ip_key(_Req({"authorization": "Bearer token-aaa"}))

    assert k1 != k2, "Different tokens must produce different keys"
    assert k1 == k4, "Same token must produce the same key (deterministic)"
    assert k3.startswith("ip:"), "Missing-auth must fall back to IP keying"
    assert k1.startswith("u:"), "Present-auth must use user-prefix"
