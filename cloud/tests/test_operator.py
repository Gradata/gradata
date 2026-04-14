"""Tests for /admin/* operator (god-mode) endpoints."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from app.auth import require_operator
from app.main import create_app


_JWT_KEY = os.environ.get("GRADATA_SUPABASE_JWT_KEY", "test-only-hmac-not-a-real-credential-x")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _jwt(email: str | None = None, sub: str = "user-1") -> str:
    claims: dict = {"sub": sub}
    if email is not None:
        claims["email"] = email
    return jwt.encode(claims, _JWT_KEY, algorithm="HS256")


def _headers(email: str | None = "oliver@gradata.ai") -> dict:
    return {"Authorization": f"Bearer {_jwt(email=email)}"}


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture
def operator_client(mock_supabase):
    """Test client with require_operator dependency forced to allow."""
    app = create_app()
    app.dependency_overrides[require_operator] = lambda: "user-1"
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------


def test_global_kpis_rejects_non_operator_email(client, mock_supabase):
    """A non-allowlisted email (even with a valid JWT) must 403."""
    resp = client.get("/api/v1/admin/global-kpis", headers=_headers("random@example.com"))
    assert resp.status_code == 403


def test_global_kpis_rejects_missing_email(client, mock_supabase):
    """No email claim + no DB match -> 403, not 500."""
    resp = client.get("/api/v1/admin/global-kpis", headers=_headers(email=None))
    assert resp.status_code == 403


def test_global_kpis_allows_gradata_email(client, mock_supabase):
    """@gradata.ai passes the gate (200 even with no workspaces)."""
    resp = client.get("/api/v1/admin/global-kpis", headers=_headers("oliver@gradata.ai"))
    assert resp.status_code == 200
    assert resp.json()["customers_total"] == 0


def test_global_kpis_allows_sprites_email(client, mock_supabase):
    """@sprites.ai also passes."""
    resp = client.get("/api/v1/admin/global-kpis", headers=_headers("anna@sprites.ai"))
    assert resp.status_code == 200


def test_global_kpis_rejects_no_auth(client, mock_supabase):
    resp = client.get("/api/v1/admin/global-kpis")
    # FastAPI's HTTPBearer returns 403 by default but app wrappers can surface 401.
    assert resp.status_code in {401, 403}


# ---------------------------------------------------------------------------
# Global KPIs aggregation
# ---------------------------------------------------------------------------


def test_global_kpis_aggregates_mrr(operator_client, mock_supabase):
    """2 pro + 1 team -> MRR = 29*2 + 99 = 157; ARR = 1884."""
    now = _now()
    mock_supabase.add_response(
        "workspaces",
        "select",
        [
            {"id": "w1", "plan": "pro", "created_at": _iso(now - timedelta(days=2)), "deleted_at": None},
            {"id": "w2", "plan": "pro", "created_at": _iso(now - timedelta(days=3)), "deleted_at": None},
            {"id": "w3", "plan": "team", "created_at": _iso(now - timedelta(days=4)), "deleted_at": None},
            {"id": "w4", "plan": "free", "created_at": _iso(now - timedelta(days=5)), "deleted_at": None},
        ],
    )
    mock_supabase.add_response(
        "brains",
        "select",
        [
            {"id": "b1", "workspace_id": "w1", "user_id": "u1", "last_sync_at": _iso(now - timedelta(days=1))},
            {"id": "b2", "workspace_id": "w2", "user_id": "u2", "last_sync_at": _iso(now - timedelta(days=20))},
        ],
    )

    resp = operator_client.get("/api/v1/admin/global-kpis")
    assert resp.status_code == 200
    data = resp.json()
    assert data["mrr_usd"] == 157.0
    assert data["arr_usd"] == 157.0 * 12
    assert data["customers_total"] == 4
    # Only w1 synced within 14 days
    assert data["customers_active"] == 1
    # NRR placeholder
    assert data["net_revenue_retention"] == 1.0


def test_global_kpis_enterprise_default_rate(operator_client, mock_supabase):
    """Enterprise plan contributes a default rate ($500) to MRR until real
    Stripe-invoiced amounts are mirrored. Override later by reading
    stripe_customer.balance instead of a fixed default.
    """
    mock_supabase.add_response(
        "workspaces",
        "select",
        [
            {"id": "w1", "plan": "enterprise", "created_at": _iso(_now()), "deleted_at": None},
            {"id": "w2", "plan": "pro", "created_at": _iso(_now()), "deleted_at": None},
        ],
    )
    mock_supabase.add_response("brains", "select", [])

    resp = operator_client.get("/api/v1/admin/global-kpis")
    assert resp.status_code == 200
    assert resp.json()["mrr_usd"] == 529.0  # 500 (enterprise default) + 29 (pro)


# ---------------------------------------------------------------------------
# Customers list — health classification, sort, paginate
# ---------------------------------------------------------------------------


def test_customers_health_classification(operator_client, mock_supabase):
    """Health buckets: <14d healthy, 14-30d at-risk, >30d or None churning."""
    now = _now()
    mock_supabase.add_response(
        "workspaces",
        "select",
        [
            {"id": "ws-healthy", "name": "Alpha", "plan": "pro", "created_at": _iso(now)},
            {"id": "ws-atrisk", "name": "Beta", "plan": "pro", "created_at": _iso(now)},
            {"id": "ws-churning", "name": "Gamma", "plan": "team", "created_at": _iso(now)},
            {"id": "ws-nosync", "name": "Delta", "plan": "free", "created_at": _iso(now)},
        ],
    )
    mock_supabase.add_response(
        "brains",
        "select",
        [
            {"id": "b1", "workspace_id": "ws-healthy", "user_id": "u1",
             "last_sync_at": _iso(now - timedelta(days=2))},
            {"id": "b2", "workspace_id": "ws-atrisk", "user_id": "u2",
             "last_sync_at": _iso(now - timedelta(days=20))},
            {"id": "b3", "workspace_id": "ws-churning", "user_id": "u3",
             "last_sync_at": _iso(now - timedelta(days=60))},
            {"id": "b4", "workspace_id": "ws-nosync", "user_id": "u4", "last_sync_at": None},
        ],
    )
    mock_supabase.add_response(
        "workspace_members",
        "select",
        [
            {"workspace_id": "ws-healthy", "user_id": "u1"},
            {"workspace_id": "ws-atrisk", "user_id": "u2"},
            {"workspace_id": "ws-churning", "user_id": "u3"},
            {"workspace_id": "ws-nosync", "user_id": "u4"},
        ],
    )

    resp = operator_client.get("/api/v1/admin/customers")
    assert resp.status_code == 200
    rows = {r["id"]: r for r in resp.json()}
    assert rows["ws-healthy"]["health"] == "healthy"
    assert rows["ws-atrisk"]["health"] == "at-risk"
    assert rows["ws-churning"]["health"] == "churning"
    assert rows["ws-nosync"]["health"] == "churning"
    assert rows["ws-healthy"]["brains"] == 1
    assert rows["ws-healthy"]["active_users"] == 1


def test_customers_sort_by_mrr_desc(operator_client, mock_supabase):
    now = _now()
    mock_supabase.add_response(
        "workspaces",
        "select",
        [
            {"id": "w1", "name": "Cheap", "plan": "free", "created_at": _iso(now)},
            {"id": "w2", "name": "Top", "plan": "team", "created_at": _iso(now)},
            {"id": "w3", "name": "Mid", "plan": "pro", "created_at": _iso(now)},
        ],
    )
    mock_supabase.add_response("brains", "select", [])
    mock_supabase.add_response("workspace_members", "select", [])

    resp = operator_client.get("/api/v1/admin/customers?sort=mrr&order=desc")
    assert resp.status_code == 200
    ids = [r["id"] for r in resp.json()]
    assert ids == ["w2", "w3", "w1"]


def test_customers_paginate(operator_client, mock_supabase):
    now = _now()
    workspaces = [
        {"id": f"w{i}", "name": f"Co{i}", "plan": "pro", "created_at": _iso(now)}
        for i in range(5)
    ]
    mock_supabase.add_response("workspaces", "select", workspaces)
    mock_supabase.add_response("brains", "select", [])
    mock_supabase.add_response("workspace_members", "select", [])

    resp = operator_client.get("/api/v1/admin/customers?limit=2&offset=1&sort=mrr&order=desc")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_customers_rejects_bad_sort(operator_client, mock_supabase):
    mock_supabase.add_response("workspaces", "select", [])
    mock_supabase.add_response("brains", "select", [])
    mock_supabase.add_response("workspace_members", "select", [])

    resp = operator_client.get("/api/v1/admin/customers?sort=bogus")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------


def test_alerts_churn_risk_for_stale_workspace(operator_client, mock_supabase):
    """Workspace whose latest brain sync is 14+ days old -> churn-risk alert."""
    now = _now()
    mock_supabase.add_response(
        "workspaces",
        "select",
        [
            {"id": "ws-stale", "name": "Stale Co", "plan": "pro", "subscription_status": "active"},
            {"id": "ws-fresh", "name": "Fresh Co", "plan": "pro", "subscription_status": "active"},
        ],
    )
    mock_supabase.add_response(
        "brains",
        "select",
        [
            {"id": "b-stale", "workspace_id": "ws-stale", "user_id": "u1",
             "last_sync_at": _iso(now - timedelta(days=20))},
            {"id": "b-fresh", "workspace_id": "ws-fresh", "user_id": "u2",
             "last_sync_at": _iso(now - timedelta(days=1))},
        ],
    )
    # No corrections -> no usage-spike noise
    mock_supabase.add_response("corrections", "select", [])

    resp = operator_client.get("/api/v1/admin/alerts")
    assert resp.status_code == 200
    kinds = [(a["kind"], a["customer"]) for a in resp.json()]
    assert ("churn-risk", "Stale Co") in kinds
    assert ("churn-risk", "Fresh Co") not in kinds


def test_alerts_failed_payment_from_subscription_status(operator_client, mock_supabase):
    """Workspace with subscription_status=past_due surfaces a failed-payment alert."""
    now = _now()
    mock_supabase.add_response(
        "workspaces",
        "select",
        [
            {"id": "ws-late", "name": "Late Payer", "plan": "pro",
             "subscription_status": "past_due"},
        ],
    )
    # Fresh sync -> skip churn-risk noise
    mock_supabase.add_response(
        "brains",
        "select",
        [
            {"id": "b-late", "workspace_id": "ws-late", "user_id": "u1",
             "last_sync_at": _iso(now - timedelta(hours=1))},
        ],
    )
    mock_supabase.add_response("corrections", "select", [])

    resp = operator_client.get("/api/v1/admin/alerts")
    assert resp.status_code == 200
    kinds = [a["kind"] for a in resp.json()]
    assert "failed-payment" in kinds


def test_alerts_rejects_non_operator(client, mock_supabase):
    resp = client.get("/api/v1/admin/alerts", headers=_headers("guest@example.com"))
    assert resp.status_code == 403


def test_customers_rejects_non_operator(client, mock_supabase):
    resp = client.get("/api/v1/admin/customers", headers=_headers("guest@example.com"))
    assert resp.status_code == 403
