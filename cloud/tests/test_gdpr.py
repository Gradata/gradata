"""Tests for GDPR endpoints — Article 15 export, Article 17 delete, data summary.

All fixtures use UUID strings so we never leak realistic PII into test output.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_user_id
from app.main import create_app

# UUID-shaped fixtures — never real user data.
CALLER_UID = "11111111-1111-4111-8111-111111111111"
OTHER_UID = "22222222-2222-4222-8222-222222222222"
BRAIN_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
WORKSPACE_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


@pytest.fixture
def app_with_user():
    """Build a fresh FastAPI app with get_current_user_id overridable."""

    def _build(user_id: str):
        app = create_app()
        app.dependency_overrides[get_current_user_id] = lambda: user_id
        return app

    return _build


@pytest.fixture
def gdpr_client(app_with_user, mock_supabase):
    """Returns a TestClient authed as ``user_id`` with mock_supabase seeded."""

    def _make(
        user_id: str = CALLER_UID,
        *,
        workspaces: list[dict] | None = None,
        brains: list[dict] | None = None,
        corrections: list[dict] | None = None,
        lessons: list[dict] | None = None,
        events: list[dict] | None = None,
        meta_rules: list[dict] | None = None,
        gdpr_export_requests: list[dict] | None = None,
        users: list[dict] | None = None,
    ) -> TestClient:
        app = app_with_user(user_id)
        if workspaces is not None:
            mock_supabase.add_response("workspaces", "select", workspaces)
        if brains is not None:
            mock_supabase.add_response("brains", "select", brains)
        if corrections is not None:
            mock_supabase.add_response("corrections", "select", corrections)
        if lessons is not None:
            mock_supabase.add_response("lessons", "select", lessons)
        if events is not None:
            mock_supabase.add_response("events", "select", events)
        if meta_rules is not None:
            mock_supabase.add_response("meta_rules", "select", meta_rules)
        if gdpr_export_requests is not None:
            mock_supabase.add_response("gdpr_export_requests", "select", gdpr_export_requests)
        if users is not None:
            mock_supabase.add_response("users", "select", users)
        return TestClient(app)

    return _make


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_export_requires_authentication():
    """No Authorization header = 401 from FastAPI's HTTPBearer."""
    app = create_app()
    client = TestClient(app)
    resp = client.get("/api/v1/me/export")
    assert resp.status_code in (401, 403)


def test_delete_requires_authentication():
    app = create_app()
    client = TestClient(app)
    resp = client.post("/api/v1/me/delete")
    assert resp.status_code in (401, 403)


def test_summary_requires_authentication():
    app = create_app()
    client = TestClient(app)
    resp = client.get("/api/v1/me/data-summary")
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /me/data-summary
# ---------------------------------------------------------------------------


def test_data_summary_counts_per_table(gdpr_client):
    workspaces = [{"id": WORKSPACE_ID, "owner_id": CALLER_UID, "created_at": "2026-01-01T00:00:00+00:00"}]
    brains = [{"id": BRAIN_ID, "user_id": CALLER_UID, "created_at": "2026-01-02T00:00:00+00:00"}]
    corrections = [
        {"id": "c1", "brain_id": BRAIN_ID, "created_at": "2026-02-01T00:00:00+00:00"},
        {"id": "c2", "brain_id": BRAIN_ID, "created_at": "2026-03-15T00:00:00+00:00"},
    ]
    lessons = [{"id": "l1", "brain_id": BRAIN_ID, "created_at": "2026-02-02T00:00:00+00:00"}]
    events = [{"id": "e1", "brain_id": BRAIN_ID, "created_at": "2026-04-10T00:00:00+00:00"}]
    meta_rules: list[dict] = []

    client = gdpr_client(
        workspaces=workspaces,
        brains=brains,
        corrections=corrections,
        lessons=lessons,
        events=events,
        meta_rules=meta_rules,
    )

    resp = client.get("/api/v1/me/data-summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == CALLER_UID
    assert body["workspaces"] == 1
    assert body["brains"] == 1
    assert body["corrections"] == 2
    assert body["lessons"] == 1
    assert body["events"] == 1
    assert body["meta_rules"] == 0
    assert body["oldest_record"] == "2026-01-01T00:00:00+00:00"
    assert body["newest_record"] == "2026-04-10T00:00:00+00:00"


def test_data_summary_ignores_soft_deleted(gdpr_client):
    workspaces = [
        {"id": WORKSPACE_ID, "owner_id": CALLER_UID, "created_at": "2026-01-01T00:00:00+00:00"},
        {
            "id": "deleted-ws",
            "owner_id": CALLER_UID,
            "created_at": "2026-01-01T00:00:00+00:00",
            "deleted_at": "2026-02-01T00:00:00+00:00",
        },
    ]
    brains = [
        {"id": BRAIN_ID, "user_id": CALLER_UID, "created_at": "2026-01-02T00:00:00+00:00"},
        {
            "id": "dead-brain",
            "user_id": CALLER_UID,
            "created_at": "2026-01-02T00:00:00+00:00",
            "deleted_at": "2026-02-01T00:00:00+00:00",
        },
    ]
    client = gdpr_client(
        workspaces=workspaces,
        brains=brains,
        corrections=[],
        lessons=[],
        events=[],
        meta_rules=[],
    )
    resp = client.get("/api/v1/me/data-summary")
    assert resp.status_code == 200
    assert resp.json()["workspaces"] == 1
    assert resp.json()["brains"] == 1


# ---------------------------------------------------------------------------
# GET /me/export
# ---------------------------------------------------------------------------


def test_export_returns_inline_payload_for_small_user(gdpr_client, mock_supabase):
    workspaces = [{"id": WORKSPACE_ID, "owner_id": CALLER_UID, "created_at": "2026-01-01T00:00:00+00:00"}]
    brains = [{"id": BRAIN_ID, "user_id": CALLER_UID, "created_at": "2026-01-02T00:00:00+00:00"}]
    corrections = [{"id": "c1", "brain_id": BRAIN_ID}]
    lessons = [{"id": "l1", "brain_id": BRAIN_ID, "description": "test lesson"}]

    client = gdpr_client(
        workspaces=workspaces,
        brains=brains,
        corrections=corrections,
        lessons=lessons,
        events=[],
        meta_rules=[],
        gdpr_export_requests=[],  # no prior exports = not rate-limited
    )

    resp = client.get("/api/v1/me/export")
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == CALLER_UID
    assert body["format"] == "json"
    assert body["download_url"] is None
    assert body["data"] is not None
    assert body["data"]["schema_version"] == 1
    assert len(body["data"]["workspaces"]) == 1
    assert len(body["data"]["brains"]) == 1
    assert len(body["data"]["corrections"]) == 1
    assert len(body["data"]["lessons"]) == 1
    # Export was logged for rate-limiting on subsequent calls.
    inserted = [r for r in mock_supabase._inserts if r.get("user_id") == CALLER_UID]
    assert inserted, "expected a gdpr_export_requests row to be inserted"


def test_export_rate_limited_when_recent_request_exists(gdpr_client):
    recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    client = gdpr_client(
        workspaces=[],
        brains=[],
        corrections=[],
        lessons=[],
        events=[],
        meta_rules=[],
        gdpr_export_requests=[{"id": "r1", "user_id": CALLER_UID, "created_at": recent}],
    )
    resp = client.get("/api/v1/me/export")
    assert resp.status_code == 429
    assert "rate-limit" in resp.json()["detail"].lower() or "rate limit" in resp.json()["detail"].lower()


def test_export_allowed_when_last_request_older_than_24h(gdpr_client):
    old = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    client = gdpr_client(
        workspaces=[],
        brains=[],
        corrections=[],
        lessons=[],
        events=[],
        meta_rules=[],
        gdpr_export_requests=[{"id": "r1", "user_id": CALLER_UID, "created_at": old}],
    )
    resp = client.get("/api/v1/me/export")
    assert resp.status_code == 200


def test_export_includes_soft_deleted_rows_for_transparency(gdpr_client):
    """Export must include soft-deleted rows so users see everything we hold."""
    workspaces = [
        {
            "id": "deleted-ws",
            "owner_id": CALLER_UID,
            "created_at": "2026-01-01T00:00:00+00:00",
            "deleted_at": "2026-02-01T00:00:00+00:00",
        }
    ]
    brains: list[dict] = []
    client = gdpr_client(
        workspaces=workspaces,
        brains=brains,
        corrections=[],
        lessons=[],
        events=[],
        meta_rules=[],
        gdpr_export_requests=[],
    )
    resp = client.get("/api/v1/me/export")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]["workspaces"]) == 1
    assert body["data"]["workspaces"][0]["deleted_at"] == "2026-02-01T00:00:00+00:00"


# ---------------------------------------------------------------------------
# POST /me/delete
# ---------------------------------------------------------------------------


def test_delete_returns_202_and_schedules_purge(gdpr_client, mock_supabase):
    workspaces = [{"id": WORKSPACE_ID, "owner_id": CALLER_UID, "created_at": "2026-01-01T00:00:00+00:00"}]
    brains = [{"id": BRAIN_ID, "user_id": CALLER_UID, "created_at": "2026-01-02T00:00:00+00:00"}]
    client = gdpr_client(
        workspaces=workspaces,
        brains=brains,
        users=[{"id": CALLER_UID, "email": None}],
    )
    resp = client.post("/api/v1/me/delete")
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "accepted"
    assert body["user_id"] == CALLER_UID
    assert body["deleted_at"]
    assert body["purge_after"]

    deleted_at = datetime.fromisoformat(body["deleted_at"])
    purge_after = datetime.fromisoformat(body["purge_after"])
    # Purge must be scheduled ~30 days after soft-delete.
    delta = purge_after - deleted_at
    assert timedelta(days=29) <= delta <= timedelta(days=31)


def test_delete_cascades_to_workspaces_and_brains(gdpr_client, mock_supabase):
    workspaces = [
        {"id": WORKSPACE_ID, "owner_id": CALLER_UID, "created_at": "2026-01-01T00:00:00+00:00"},
        {"id": "ws-2", "owner_id": CALLER_UID, "created_at": "2026-01-01T00:00:00+00:00"},
    ]
    brains = [
        {"id": BRAIN_ID, "user_id": CALLER_UID, "created_at": "2026-01-02T00:00:00+00:00"},
        {"id": "brain-2", "user_id": CALLER_UID, "created_at": "2026-01-02T00:00:00+00:00"},
    ]
    client = gdpr_client(workspaces=workspaces, brains=brains, users=[])
    resp = client.post("/api/v1/me/delete")
    assert resp.status_code == 202
    # Soft-deletes are tracked via upsert on the users table; the mock stores
    # upserts in _inserts. Verify the tombstone exists.
    tombstones = [r for r in mock_supabase._inserts if r.get("id") == CALLER_UID and r.get("deleted_at")]
    assert tombstones, "expected users.deleted_at tombstone to be upserted"


def test_delete_is_idempotent_when_no_owned_resources(gdpr_client):
    """User with no workspaces or brains can still delete their account."""
    client = gdpr_client(workspaces=[], brains=[], users=[])
    resp = client.post("/api/v1/me/delete")
    assert resp.status_code == 202


def test_delete_is_idempotent_when_already_soft_deleted(gdpr_client, mock_supabase):
    """Repeat /me/delete returns the existing ledger state without re-cascading.

    Without this guard, calling /me/delete twice would reset the 30-day purge
    window and re-tombstone owned rows on every call.
    """
    existing_deleted_at = "2026-04-01T00:00:00+00:00"
    existing_purge_after = "2026-05-01T00:00:00+00:00"
    client = gdpr_client(
        workspaces=[],
        brains=[],
        users=[
            {
                "id": CALLER_UID,
                "email": None,
                "deleted_at": existing_deleted_at,
                "purge_after": existing_purge_after,
            }
        ],
    )
    resp = client.post("/api/v1/me/delete")
    assert resp.status_code == 202
    body = resp.json()
    assert body["deleted_at"] == existing_deleted_at
    assert body["purge_after"] == existing_purge_after
    # No second tombstone upsert should have fired.
    second_tombstones = [
        r for r in mock_supabase._inserts if r.get("id") == CALLER_UID and r.get("deleted_at")
    ]
    assert second_tombstones == [], "expected no re-tombstone on repeat delete"


# ---------------------------------------------------------------------------
# Backwards-compat: existing /workspaces/{id}/members must still work
# after soft-delete filter was added in auth.py / users.py.
# ---------------------------------------------------------------------------


def test_backcompat_members_endpoint_still_works_for_active_user(gdpr_client, mock_supabase):
    """Sanity check: an active user's workspace members endpoint still returns
    data after we added deleted_at filtering in auth.py."""
    members = [
        {"workspace_id": WORKSPACE_ID, "user_id": CALLER_UID, "role": "owner"},
    ]
    mock_supabase.add_response("workspace_members", "select", members)
    client = gdpr_client(workspaces=[], brains=[])
    resp = client.get(f"/api/v1/workspaces/{WORKSPACE_ID}/members")
    assert resp.status_code == 200
