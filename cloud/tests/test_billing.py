"""Tests for /billing/checkout, /billing/portal, and /billing/webhook routes."""

from __future__ import annotations

import json
import sys
import types
from unittest.mock import MagicMock

import pytest

from app.config import get_settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def stub_user(client):
    """Bypass JWT verification — return a fixed user_id from get_current_user_id."""
    from app.auth import get_current_user_id

    async def _stub_get_user_id():
        return "user-1"

    client.app.dependency_overrides[get_current_user_id] = _stub_get_user_id
    yield
    client.app.dependency_overrides.pop(get_current_user_id, None)


@pytest.fixture
def configured_prices(monkeypatch):
    """Set Stripe price IDs in settings (use cache_clear so values stick)."""
    get_settings.cache_clear()
    monkeypatch.setenv("GRADATA_STRIPE_PRICE_ID_CLOUD", "price_cloud_test")
    monkeypatch.setenv("GRADATA_STRIPE_PRICE_ID_TEAM", "price_team_test")
    monkeypatch.setenv("GRADATA_STRIPE_SECRET_KEY", "sk_test_dummy")
    monkeypatch.setenv("GRADATA_STRIPE_WEBHOOK_SECRET", "whsec_test_dummy")
    yield
    get_settings.cache_clear()


@pytest.fixture
def unconfigured_prices(monkeypatch):
    """Explicitly clear price IDs so checkout returns 503."""
    get_settings.cache_clear()
    monkeypatch.delenv("GRADATA_STRIPE_PRICE_ID_CLOUD", raising=False)
    monkeypatch.delenv("GRADATA_STRIPE_PRICE_ID_TEAM", raising=False)
    monkeypatch.setenv("GRADATA_STRIPE_SECRET_KEY", "sk_test_dummy")
    monkeypatch.setenv("GRADATA_STRIPE_WEBHOOK_SECRET", "whsec_test_dummy")
    yield
    get_settings.cache_clear()


@pytest.fixture
def fake_stripe(monkeypatch):
    """Install a stub `stripe` module so the lazy import in routes returns our mock."""
    fake_module = types.ModuleType("stripe")

    fake_module.checkout = types.SimpleNamespace(
        Session=types.SimpleNamespace(
            create=MagicMock(return_value=types.SimpleNamespace(url="https://stripe.test/checkout/sess_1"))
        )
    )
    fake_module.billing_portal = types.SimpleNamespace(
        Session=types.SimpleNamespace(
            create=MagicMock(return_value=types.SimpleNamespace(url="https://billing.stripe.test/portal_1"))
        )
    )

    class _SigErr(Exception):
        pass

    fake_module.error = types.SimpleNamespace(SignatureVerificationError=_SigErr)
    fake_module.Webhook = types.SimpleNamespace(construct_event=MagicMock())

    monkeypatch.setitem(sys.modules, "stripe", fake_module)
    return fake_module


def _auth_headers() -> dict:
    """Bearer header — actual JWT verification is stubbed by `stub_user`."""
    return {"Authorization": "Bearer dummy.jwt.token"}


# ---------------------------------------------------------------------------
# /billing/checkout — validation
# ---------------------------------------------------------------------------


class TestCheckoutValidation:
    def test_rejects_invalid_plan_value(self, client, stub_user, configured_prices, fake_stripe):
        """Unknown plan values fail Pydantic enum validation -> 422."""
        resp = client.post(
            "/api/v1/billing/checkout",
            json={"plan": "pro"},  # legacy/stale tier
            headers=_auth_headers(),
        )
        assert resp.status_code == 422

    def test_rejects_garbage_plan(self, client, stub_user, configured_prices, fake_stripe):
        resp = client.post(
            "/api/v1/billing/checkout",
            json={"plan": "platinum-deluxe"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 422

    def test_rejects_enterprise_with_400(self, client, stub_user, configured_prices, fake_stripe):
        """Enterprise tier is sales-only — rejected with 400 + contact-sales message."""
        resp = client.post(
            "/api/v1/billing/checkout",
            json={"plan": "enterprise"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 400
        assert "contact sales" in resp.json()["detail"].lower()

    def test_rejects_free_with_400(self, client, stub_user, configured_prices, fake_stripe):
        """Free plan does not require checkout."""
        resp = client.post(
            "/api/v1/billing/checkout",
            json={"plan": "free"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 400

    def test_returns_503_when_price_id_missing(
        self, client, stub_user, unconfigured_prices, fake_stripe
    ):
        """If the configured price_id is empty, checkout returns 503 not_configured."""
        resp = client.post(
            "/api/v1/billing/checkout",
            json={"plan": "cloud"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 503
        assert "not configured" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# /billing/checkout — happy path
# ---------------------------------------------------------------------------


class TestCheckoutHappyPath:
    def test_cloud_plan_uses_cloud_price_id(
        self, client, stub_user, configured_prices, fake_stripe
    ):
        resp = client.post(
            "/api/v1/billing/checkout",
            json={"plan": "cloud"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["checkout_url"] == "https://stripe.test/checkout/sess_1"

        call_kwargs = fake_stripe.checkout.Session.create.call_args.kwargs
        assert call_kwargs["line_items"][0]["price"] == "price_cloud_test"
        assert call_kwargs["mode"] == "subscription"
        assert call_kwargs["metadata"]["user_id"] == "user-1"
        assert call_kwargs["metadata"]["plan"] == "cloud"

    def test_team_plan_uses_team_price_id(
        self, client, stub_user, configured_prices, fake_stripe
    ):
        fake_stripe.checkout.Session.create.reset_mock()
        resp = client.post(
            "/api/v1/billing/checkout",
            json={"plan": "team"},
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        call_kwargs = fake_stripe.checkout.Session.create.call_args.kwargs
        assert call_kwargs["line_items"][0]["price"] == "price_team_test"


# ---------------------------------------------------------------------------
# /billing/portal
# ---------------------------------------------------------------------------


class TestPortal:
    def test_returns_404_when_no_workspace(
        self, client, mock_supabase, stub_user, configured_prices, fake_stripe
    ):
        # No workspace rows for user-1
        resp = client.post("/api/v1/billing/portal", headers=_auth_headers())
        assert resp.status_code == 404
        assert "no active subscription" in resp.json()["detail"].lower()

    def test_returns_404_when_no_stripe_customer_id(
        self, client, mock_supabase, stub_user, configured_prices, fake_stripe
    ):
        mock_supabase.add_response(
            "workspaces",
            "select",
            [{"owner_id": "user-1", "stripe_customer_id": None}],
        )
        resp = client.post("/api/v1/billing/portal", headers=_auth_headers())
        assert resp.status_code == 404

    def test_returns_portal_url_when_customer_exists(
        self, client, mock_supabase, stub_user, configured_prices, fake_stripe
    ):
        mock_supabase.add_response(
            "workspaces",
            "select",
            [{"owner_id": "user-1", "stripe_customer_id": "cus_test_123"}],
        )
        resp = client.post("/api/v1/billing/portal", headers=_auth_headers())
        assert resp.status_code == 200
        assert resp.json()["url"] == "https://billing.stripe.test/portal_1"

        call_kwargs = fake_stripe.billing_portal.Session.create.call_args.kwargs
        assert call_kwargs["customer"] == "cus_test_123"


# ---------------------------------------------------------------------------
# /billing/webhook — event dispatching
# ---------------------------------------------------------------------------


class TestWebhook:
    def _post_event(self, client, fake_stripe, event: dict):
        fake_stripe.Webhook.construct_event = MagicMock(return_value=event)
        return client.post(
            "/api/v1/billing/webhook",
            content=json.dumps(event),
            headers={"stripe-signature": "test-sig"},
        )

    def test_subscription_updated_writes_plan_to_workspace(
        self, client, mock_supabase, configured_prices, fake_stripe
    ):
        captured: list[dict] = []

        async def _capture_update(table, data, filters=None):
            captured.append({"table": table, "data": data, "filters": filters})
            return [data]

        mock_supabase.update = _capture_update  # type: ignore[method-assign]
        if True:
            event = {
                "type": "customer.subscription.updated",
                "data": {
                    "object": {
                        "customer": "cus_test_123",
                        "status": "active",
                        "current_period_end": 1700000000,
                        "metadata": {"plan": "team"},
                    }
                },
            }
            resp = self._post_event(client, fake_stripe, event)

        assert resp.status_code == 200
        assert len(captured) == 1
        assert captured[0]["table"] == "workspaces"
        assert captured[0]["data"]["plan"] == "team"
        assert captured[0]["data"]["subscription_status"] == "active"
        assert captured[0]["filters"]["stripe_customer_id"] == "cus_test_123"

    def test_subscription_deleted_downgrades_to_free(
        self, client, mock_supabase, configured_prices, fake_stripe
    ):
        captured: list[dict] = []

        async def _capture_update(table, data, filters=None):
            captured.append({"table": table, "data": data, "filters": filters})
            return [data]

        mock_supabase.update = _capture_update  # type: ignore[method-assign]
        if True:
            event = {
                "type": "customer.subscription.deleted",
                "data": {
                    "object": {"customer": "cus_test_123", "status": "canceled"}
                },
            }
            resp = self._post_event(client, fake_stripe, event)

        assert resp.status_code == 200
        assert captured[0]["data"]["plan"] == "free"
        assert captured[0]["data"]["subscription_status"] == "canceled"

    def test_invoice_payment_failed_marks_past_due(
        self, client, mock_supabase, configured_prices, fake_stripe
    ):
        captured: list[dict] = []

        async def _capture_update(table, data, filters=None):
            captured.append({"table": table, "data": data, "filters": filters})
            return [data]

        mock_supabase.update = _capture_update  # type: ignore[method-assign]
        if True:
            event = {
                "type": "invoice.payment_failed",
                "data": {"object": {"customer": "cus_test_123"}},
            }
            resp = self._post_event(client, fake_stripe, event)

        assert resp.status_code == 200
        assert captured[0]["data"]["subscription_status"] == "past_due"

    def test_invalid_signature_returns_400(
        self, client, mock_supabase, configured_prices, fake_stripe
    ):
        def _raise(*_a, **_kw):
            raise fake_stripe.error.SignatureVerificationError("bad sig")

        fake_stripe.Webhook.construct_event = MagicMock(side_effect=_raise)
        resp = client.post(
            "/api/v1/billing/webhook",
            content=b"{}",
            headers={"stripe-signature": "wrong"},
        )
        assert resp.status_code == 400
