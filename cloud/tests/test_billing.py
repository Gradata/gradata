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
        # Inject defaults so hardening checks pass: every real Stripe event
        # carries both `id` and `created`. Individual tests can override.
        import time as _time
        event.setdefault("id", f"evt_test_{id(event)}")
        event.setdefault("created", int(_time.time()))
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
        # The webhook handler also updates processed_webhooks to flip
        # status=processing -> processed; filter to workspace writes only.
        workspace_writes = [c for c in captured if c["table"] == "workspaces"]
        assert len(workspace_writes) == 1
        assert workspace_writes[0]["data"]["plan"] == "team"
        assert workspace_writes[0]["data"]["subscription_status"] == "active"
        assert workspace_writes[0]["filters"]["stripe_customer_id"] == "cus_test_123"

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
        workspace_writes = [c for c in captured if c["table"] == "workspaces"]
        assert workspace_writes[0]["data"]["plan"] == "free"
        assert workspace_writes[0]["data"]["subscription_status"] == "canceled"

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
        workspace_writes = [c for c in captured if c["table"] == "workspaces"]
        assert workspace_writes[0]["data"]["subscription_status"] == "past_due"

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


# ---------------------------------------------------------------------------
# /billing/webhook — hardening: idempotency + replay protection
# ---------------------------------------------------------------------------


class TestWebhookHardening:
    def _post_with(self, client, fake_stripe, event: dict):
        """Post a raw event dict without the id/created defaults.

        Unlike TestWebhook._post_event (which calls setdefault for `id` and
        `created`), hardening tests need to control those fields exactly —
        e.g., stale-event tests supply their own `created`, and the
        missing-`created` test deliberately omits it. Don't add defaults here.
        """
        fake_stripe.Webhook.construct_event = MagicMock(return_value=event)
        return client.post(
            "/api/v1/billing/webhook",
            content=json.dumps(event),
            headers={"stripe-signature": "test-sig"},
        )

    def test_rejects_stale_event_older_than_five_minutes(
        self, client, mock_supabase, configured_prices, fake_stripe
    ):
        """Events where `created` is > 5min old must 400 (replay protection)."""
        import time as _time
        stale_event = {
            "id": "evt_replay_1",
            "type": "customer.subscription.updated",
            "created": int(_time.time()) - (6 * 60),  # 6 min old
            "data": {"object": {"customer": "cus_x"}},
        }
        resp = self._post_with(client, fake_stripe, stale_event)
        assert resp.status_code == 400
        assert "too old" in resp.json()["detail"].lower()

    def test_rejects_event_missing_created_field(
        self, client, mock_supabase, configured_prices, fake_stripe
    ):
        """Signature-verified events missing `created` are treated as malformed."""
        event = {
            "id": "evt_no_ts",
            "type": "customer.subscription.updated",
            "data": {"object": {"customer": "cus_x"}},
        }
        resp = self._post_with(client, fake_stripe, event)
        assert resp.status_code == 400

    def test_duplicate_event_id_returns_200_without_reprocessing(
        self, client, mock_supabase, configured_prices, fake_stripe
    ):
        """Once an event.id is in processed_webhooks, re-delivery is a no-op."""
        import time as _time

        # Seed the idempotency table with a COMPLETED row for this event_id.
        # Only status='processed' short-circuits; a bare row (or one stuck in
        # 'processing') would be treated as a stale/poisoned claim instead.
        mock_supabase.add_response(
            "processed_webhooks", "select",
            [{"event_id": "evt_duplicate_1", "status": "processed"}],
        )

        # Capture update calls so we can assert the handler did NOT run.
        captured: list[dict] = []

        async def _capture_update(table, data, filters=None):
            captured.append({"table": table, "data": data, "filters": filters})
            return [data]

        mock_supabase.update = _capture_update  # type: ignore[method-assign]

        event = {
            "id": "evt_duplicate_1",
            "type": "customer.subscription.updated",
            "created": int(_time.time()),
            "data": {"object": {"customer": "cus_x", "status": "active"}},
        }
        resp = self._post_with(client, fake_stripe, event)

        assert resp.status_code == 200
        body = resp.json()
        assert body.get("duplicate") is True
        assert not captured, "Handler must NOT run for duplicate events"

    def test_new_event_id_is_recorded_in_processed_webhooks(
        self, client, mock_supabase, configured_prices, fake_stripe
    ):
        """Claim-first design: a new event.id is INSERTED (claim) before handling.

        Atomicity guarantee: the row exists with status='processing' from the
        moment the handler starts, so a concurrent delivery's PK conflict is
        what blocks double-apply — not a post-success insert.
        """
        import time as _time

        inserts: list[dict] = []
        updates: list[dict] = []

        async def _capture_insert(table, data):
            inserts.append({"table": table, "data": data})
            return [data] if isinstance(data, dict) else list(data)

        async def _capture_update(table, data, filters=None):
            updates.append({"table": table, "data": data, "filters": filters})
            return [data]

        mock_supabase.insert = _capture_insert  # type: ignore[method-assign]
        mock_supabase.update = _capture_update  # type: ignore[method-assign]

        event = {
            "id": "evt_fresh_1",
            "type": "invoice.payment_failed",
            "created": int(_time.time()),
            "data": {"object": {"customer": "cus_x"}},
        }
        resp = self._post_with(client, fake_stripe, event)

        assert resp.status_code == 200
        # Exactly one claim insert with status='processing'.
        marker_rows = [row for row in inserts if row["table"] == "processed_webhooks"]
        assert len(marker_rows) == 1
        claim = marker_rows[0]["data"]
        assert claim["event_id"] == "evt_fresh_1"
        assert claim["event_type"] == "invoice.payment_failed"
        assert claim["status"] == "processing"

        # And a completion update flipping status -> processed.
        completions = [
            u for u in updates
            if u["table"] == "processed_webhooks"
            and u["data"].get("status") == "processed"
        ]
        assert len(completions) == 1
        assert completions[0]["filters"] == {"event_id": "evt_fresh_1"}

    def test_claim_race_loss_short_circuits_handler(
        self, client, mock_supabase, configured_prices, fake_stripe
    ):
        """If two deliveries race and we lose the claim, the handler MUST NOT run.

        This is the core correctness guarantee of the claim-first design: a
        concurrent delivery that inserts first wins; any later inserter gets
        a PK conflict (simulated here by insert raising). The follow-up SELECT
        sees the winner's active 'processing' row (recent claimed_at), so we
        skip processing entirely to avoid double-apply.
        """
        import time as _time
        from datetime import datetime, timedelta, timezone

        # Winner's active claim — recent claimed_at, still 'processing'.
        recent_ts = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
        mock_supabase.add_response(
            "processed_webhooks", "select",
            [{"event_id": "evt_race_loser", "status": "processing", "claimed_at": recent_ts}],
        )

        async def _raise_pk_conflict(table, data):
            # Simulate Supabase/Postgres returning 409 on PK violation.
            if table == "processed_webhooks":
                raise RuntimeError("duplicate key value violates unique constraint")
            return [data] if isinstance(data, dict) else list(data)

        handler_updates: list[dict] = []

        async def _capture_update(table, data, filters=None):
            handler_updates.append({"table": table, "data": data, "filters": filters})
            return [data]

        mock_supabase.insert = _raise_pk_conflict  # type: ignore[method-assign]
        mock_supabase.update = _capture_update  # type: ignore[method-assign]

        event = {
            "id": "evt_race_loser",
            "type": "customer.subscription.updated",
            "created": int(_time.time()),
            "data": {"object": {"customer": "cus_x", "status": "active"}},
        }
        resp = self._post_with(client, fake_stripe, event)

        assert resp.status_code == 200
        assert resp.json().get("duplicate") is True
        # Handler must NOT have touched workspaces — the winner handles it.
        workspace_writes = [u for u in handler_updates if u["table"] == "workspaces"]
        assert not workspace_writes, \
            "Claim-race loser must skip the handler to prevent double-apply"

    def test_stale_processing_claim_is_reclaimed_not_dropped(
        self, client, mock_supabase, configured_prices, fake_stripe
    ):
        """A 'processing' row older than the stale window must be reclaimed.

        Regression: without reclaim, a worker that dies mid-handler leaves a
        permanent poison-pill row that blocks every subsequent Stripe retry
        for the same event_id.
        """
        import time as _time
        from datetime import datetime, timedelta, timezone

        # Stale claim: status='processing', claimed_at 20 min ago (> 10 min window).
        stale_ts = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        mock_supabase.add_response(
            "processed_webhooks", "select",
            [{"event_id": "evt_stale_1", "status": "processing", "claimed_at": stale_ts}],
        )

        async def _raise_pk_conflict(table, data):
            if table == "processed_webhooks":
                raise RuntimeError("duplicate key value violates unique constraint")
            return [data]

        update_calls: list[dict] = []

        async def _capture_update(table, data, filters=None):
            update_calls.append({"table": table, "data": data, "filters": filters})
            return [data]

        mock_supabase.insert = _raise_pk_conflict  # type: ignore[method-assign]
        mock_supabase.update = _capture_update  # type: ignore[method-assign]

        event = {
            "id": "evt_stale_1",
            "type": "customer.subscription.updated",
            "created": int(_time.time()),
            "data": {"object": {"customer": "cus_x", "status": "active"}},
        }
        resp = self._post_with(client, fake_stripe, event)

        assert resp.status_code == 200
        # A reclaim UPDATE on processed_webhooks must have happened.
        reclaims = [
            u for u in update_calls
            if u["table"] == "processed_webhooks"
            and u["data"].get("status") == "processing"
        ]
        assert len(reclaims) == 1, "Stale processing row must be reclaimed"
        # The filter MUST include the prior claimed_at to prevent racing reclaims
        # from both winning the update.
        assert reclaims[0]["filters"].get("claimed_at") == stale_ts
        # Handler should have run (workspace update present).
        workspace_writes = [u for u in update_calls if u["table"] == "workspaces"]
        assert workspace_writes, "Handler must run after successful reclaim"

    def test_active_processing_claim_is_not_reclaimed(
        self, client, mock_supabase, configured_prices, fake_stripe
    ):
        """A 'processing' row younger than the stale window stays claimed."""
        import time as _time
        from datetime import datetime, timedelta, timezone

        # Recent claim: 30 seconds old — another worker is actively handling.
        recent_ts = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
        mock_supabase.add_response(
            "processed_webhooks", "select",
            [{"event_id": "evt_active_1", "status": "processing", "claimed_at": recent_ts}],
        )

        async def _raise_pk_conflict(table, data):
            if table == "processed_webhooks":
                raise RuntimeError("duplicate key value violates unique constraint")
            return [data]

        update_calls: list[dict] = []

        async def _capture_update(table, data, filters=None):
            update_calls.append({"table": table, "data": data, "filters": filters})
            return [data]

        mock_supabase.insert = _raise_pk_conflict  # type: ignore[method-assign]
        mock_supabase.update = _capture_update  # type: ignore[method-assign]

        event = {
            "id": "evt_active_1",
            "type": "customer.subscription.updated",
            "created": int(_time.time()),
            "data": {"object": {"customer": "cus_x", "status": "active"}},
        }
        resp = self._post_with(client, fake_stripe, event)

        assert resp.status_code == 200
        assert resp.json().get("duplicate") is True
        # No reclaim, no handler run.
        reclaims = [
            u for u in update_calls
            if u["table"] == "processed_webhooks"
            and u["data"].get("status") == "processing"
        ]
        assert not reclaims, "Active claim must NOT be reclaimed"
        workspace_writes = [u for u in update_calls if u["table"] == "workspaces"]
        assert not workspace_writes, "Handler must NOT run while another worker holds the claim"

    def test_claim_store_unavailable_returns_503_not_duplicate_ack(
        self, client, mock_supabase, configured_prices, fake_stripe
    ):
        """If the processed_webhooks store is unreachable, return 503 so Stripe retries.

        Regression (CR-CRITICAL): previously, any failure in _claim_event collapsed
        to a 200 {"duplicate": true}, which told Stripe to stop retrying even when
        we had NOT actually processed the event. A missing migration or a transient
        DB outage could silently swallow subscription/payment webhooks.
        """
        import time as _time

        async def _raise_on_insert(table, data):
            if table == "processed_webhooks":
                raise RuntimeError("relation \"processed_webhooks\" does not exist")
            return [data] if isinstance(data, dict) else list(data)

        async def _raise_on_select(
            table, columns="*", filters=None, in_=None,
        ):
            if table == "processed_webhooks":
                raise RuntimeError("relation \"processed_webhooks\" does not exist")
            return []

        handler_updates: list[dict] = []

        async def _capture_update(table, data, filters=None):
            handler_updates.append({"table": table, "data": data, "filters": filters})
            return [data]

        mock_supabase.insert = _raise_on_insert  # type: ignore[method-assign]
        mock_supabase.select = _raise_on_select  # type: ignore[method-assign]
        mock_supabase.update = _capture_update  # type: ignore[method-assign]

        event = {
            "id": "evt_store_down_1",
            "type": "customer.subscription.updated",
            "created": int(_time.time()),
            "data": {"object": {"customer": "cus_x", "status": "active"}},
        }
        resp = self._post_with(client, fake_stripe, event)

        # MUST NOT ack — Stripe has to retry until we can safely claim.
        assert resp.status_code == 503, (
            f"Store-unavailable must 5xx so Stripe retries, got {resp.status_code}: {resp.text}"
        )
        # Handler MUST NOT have run.
        workspace_writes = [u for u in handler_updates if u["table"] == "workspaces"]
        assert not workspace_writes, "Handler must NOT run when we can't safely claim"
