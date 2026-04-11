"""Tests for new endpoints: users, api-keys, brain detail, lessons, corrections, analytics, billing."""

from __future__ import annotations

import os

import pytest
from jose import jwt

# JWT fixture helpers
_JWT_KEY = os.environ.get("GRADATA_SUPABASE_JWT_KEY", "test-only-hmac-not-a-real-credential-x")


def _make_jwt(user_id: str = "user-1") -> str:
    return jwt.encode({"sub": user_id}, _JWT_KEY, algorithm="HS256")


def _jwt_headers(user_id: str = "user-1") -> dict:
    return {"Authorization": f"Bearer {_make_jwt(user_id)}"}


# ---------------------------------------------------------------------------
# /users/me
# ---------------------------------------------------------------------------


def test_get_profile(client, mock_supabase):
    mock_supabase.add_response(
        "workspace_members",
        "select",
        [{"workspace_id": "ws-1", "role": "owner", "user_id": "user-1"}],
    )
    mock_supabase.add_response("workspaces", "select", [{"id": "ws-1", "name": "My Workspace"}])
    mock_supabase.add_response(
        "brains", "select", [{"user_id": "user-1", "created_at": "2024-01-01"}]
    )

    resp = client.get("/api/v1/users/me", headers=_jwt_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == "user-1"
    assert len(data["workspaces"]) == 1


def test_patch_profile(client, mock_supabase):
    mock_supabase.add_response(
        "workspace_members",
        "select",
        [{"workspace_id": "ws-1", "role": "owner", "user_id": "user-1"}],
    )
    mock_supabase.add_response("workspaces", "select", [{"id": "ws-1", "name": "My Workspace"}])

    resp = client.patch(
        "/api/v1/users/me",
        json={"display_name": "Oliver"},
        headers=_jwt_headers(),
    )
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Oliver"


def test_get_profile_requires_jwt(client, mock_supabase, auth_headers):
    """API key auth is not accepted on /users/me."""
    resp = client.get("/api/v1/users/me", headers=auth_headers)
    # API key starts with gd_ — verify_jwt will reject it
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /api-keys
# ---------------------------------------------------------------------------


def test_list_api_keys(client, mock_supabase):
    mock_supabase.add_response(
        "brains",
        "select",
        [
            {
                "id": "brain-1",
                "user_id": "user-1",
                "api_key": "gd_live_abcdef1234567890",
                "created_at": None,
            }
        ],
    )

    resp = client.get("/api/v1/api-keys", headers=_jwt_headers())
    assert resp.status_code == 200
    keys = resp.json()
    assert len(keys) == 1
    assert keys[0]["masked_key"].endswith("7890")
    assert "gd_live" not in keys[0]["masked_key"]


def test_create_api_key(client, mock_supabase):
    mock_supabase.add_response(
        "brains",
        "select",
        [{"id": "brain-1", "user_id": "user-1"}],
    )

    resp = client.post(
        "/api/v1/api-keys",
        json={"brain_id": "brain-1", "brain_name": "default"},
        headers=_jwt_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["api_key"].startswith("gd_live_")
    assert data["brain_id"] == "brain-1"


def test_create_api_key_wrong_owner(client, mock_supabase):
    mock_supabase.add_response(
        "brains",
        "select",
        [{"id": "brain-1", "user_id": "other-user"}],
    )

    resp = client.post(
        "/api/v1/api-keys",
        json={"brain_id": "brain-1", "brain_name": "default"},
        headers=_jwt_headers("user-1"),
    )
    assert resp.status_code == 403


def test_revoke_api_key(client, mock_supabase):
    mock_supabase.add_response("brains", "select", [{"id": "brain-1", "user_id": "user-1"}])

    resp = client.delete("/api/v1/api-keys/brain-1", headers=_jwt_headers())
    assert resp.status_code == 204


def test_revoke_api_key_not_found(client, mock_supabase):
    mock_supabase.add_response("brains", "select", [])

    resp = client.delete("/api/v1/api-keys/missing", headers=_jwt_headers())
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /brains/{brain_id}
# ---------------------------------------------------------------------------


def test_get_brain_detail(client, mock_supabase, auth_headers):
    mock_supabase.add_response(
        "brains",
        "select",
        [
            {
                "id": "brain-1",
                "user_id": "user-1",
                "api_key": "gd_TVAL",
                "brain_name": "default",
                "domain": "sales",
            }
        ],
    )
    mock_supabase.add_response(
        "lessons",
        "select",
        [{"id": "l1", "brain_id": "brain-1"}, {"id": "l2", "brain_id": "brain-1"}],
    )
    mock_supabase.add_response("corrections", "select", [{"id": "c1", "brain_id": "brain-1"}])

    resp = client.get("/api/v1/brains/brain-1", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "brain-1"
    assert data["lesson_count"] == 2
    assert data["correction_count"] == 1


def test_update_brain(client, mock_supabase, auth_headers):
    mock_supabase.add_response(
        "brains",
        "select",
        [{"id": "brain-1", "user_id": "user-1", "api_key": "gd_TVAL"}],
    )
    mock_supabase.add_response("lessons", "select", [])
    mock_supabase.add_response("corrections", "select", [])

    resp = client.patch(
        "/api/v1/brains/brain-1",
        json={"brain_name": "renamed", "domain": "marketing"},
        headers=auth_headers,
    )
    assert resp.status_code == 200


def test_delete_brain(client, mock_supabase, auth_headers):
    mock_supabase.add_response(
        "brains",
        "select",
        [{"id": "brain-1", "user_id": "user-1", "api_key": "gd_TVAL"}],
    )

    resp = client.delete("/api/v1/brains/brain-1", headers=auth_headers)
    assert resp.status_code == 204


def test_get_brain_not_found(client, mock_supabase):
    # JWT auth: valid user but brain_id doesn't exist -> 404
    mock_supabase.add_response("brains", "select", [])

    resp = client.get("/api/v1/brains/missing", headers=_jwt_headers())
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /brains/{brain_id}/lessons
# ---------------------------------------------------------------------------


def test_list_lessons(client, mock_supabase, auth_headers):
    mock_supabase.add_response(
        "brains",
        "select",
        [{"id": "brain-1", "user_id": "user-1", "api_key": "gd_TVAL"}],
    )
    mock_supabase.add_response(
        "lessons",
        "select",
        [
            {
                "id": "l1",
                "brain_id": "brain-1",
                "state": "RULE",
                "category": "FORMAT",
                "confidence": 0.95,
            },
            {
                "id": "l2",
                "brain_id": "brain-1",
                "state": "PATTERN",
                "category": "LOGIC",
                "confidence": 0.65,
            },
        ],
    )

    resp = client.get("/api/v1/brains/brain-1/lessons", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_list_lessons_filter_state(client, mock_supabase, auth_headers):
    mock_supabase.add_response(
        "brains",
        "select",
        [{"id": "brain-1", "user_id": "user-1", "api_key": "gd_TVAL"}],
    )
    mock_supabase.add_response(
        "lessons",
        "select",
        [{"id": "l1", "brain_id": "brain-1", "state": "RULE", "confidence": 0.95}],
    )

    resp = client.get("/api/v1/brains/brain-1/lessons?state=RULE", headers=auth_headers)
    assert resp.status_code == 200


def test_list_lessons_min_confidence(client, mock_supabase, auth_headers):
    mock_supabase.add_response(
        "brains",
        "select",
        [{"id": "brain-1", "user_id": "user-1", "api_key": "gd_TVAL"}],
    )
    mock_supabase.add_response(
        "lessons",
        "select",
        [
            {"id": "l1", "brain_id": "brain-1", "state": "RULE", "confidence": 0.95},
            {"id": "l2", "brain_id": "brain-1", "state": "PATTERN", "confidence": 0.4},
        ],
    )

    resp = client.get("/api/v1/brains/brain-1/lessons?min_confidence=0.8", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# ---------------------------------------------------------------------------
# /brains/{brain_id}/corrections
# ---------------------------------------------------------------------------


def test_list_corrections(client, mock_supabase, auth_headers):
    mock_supabase.add_response(
        "brains",
        "select",
        [{"id": "brain-1", "user_id": "user-1", "api_key": "gd_TVAL"}],
    )
    mock_supabase.add_response(
        "corrections",
        "select",
        [
            {
                "id": "c1",
                "brain_id": "brain-1",
                "severity": "major",
                "category": "FORMAT",
                "session": 1,
            },
            {
                "id": "c2",
                "brain_id": "brain-1",
                "severity": "minor",
                "category": "LOGIC",
                "session": 2,
            },
        ],
    )

    resp = client.get("/api/v1/brains/brain-1/corrections", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_list_corrections_filter_severity(client, mock_supabase, auth_headers):
    mock_supabase.add_response(
        "brains",
        "select",
        [{"id": "brain-1", "user_id": "user-1", "api_key": "gd_TVAL"}],
    )
    mock_supabase.add_response(
        "corrections",
        "select",
        [{"id": "c1", "brain_id": "brain-1", "severity": "major"}],
    )

    resp = client.get("/api/v1/brains/brain-1/corrections?severity=major", headers=auth_headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# /brains/{brain_id}/analytics
# ---------------------------------------------------------------------------


def test_get_analytics(client, mock_supabase, auth_headers):
    mock_supabase.add_response(
        "brains",
        "select",
        [
            {
                "id": "brain-1",
                "user_id": "user-1",
                "api_key": "gd_TVAL",
                "last_sync_at": None,
                "created_at": None,
            }
        ],
    )
    mock_supabase.add_response(
        "lessons",
        "select",
        [
            {"brain_id": "brain-1", "state": "RULE", "confidence": 0.95},
            {"brain_id": "brain-1", "state": "RULE", "confidence": 0.90},
            {"brain_id": "brain-1", "state": "PATTERN", "confidence": 0.60},
        ],
    )
    mock_supabase.add_response(
        "corrections",
        "select",
        [
            {"brain_id": "brain-1", "severity": "major", "category": "FORMAT"},
            {"brain_id": "brain-1", "severity": "minor", "category": "FORMAT"},
        ],
    )
    mock_supabase.add_response(
        "events",
        "select",
        [
            {"id": "e1", "brain_id": "brain-1"},
            {"id": "e2", "brain_id": "brain-1"},
            {"id": "e3", "brain_id": "brain-1"},
        ],
    )

    resp = client.get("/api/v1/brains/brain-1/analytics", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_lessons"] == 3
    assert data["total_corrections"] == 2
    assert data["total_events"] == 3
    assert data["lessons_by_state"]["RULE"] == 2
    assert data["corrections_by_severity"]["major"] == 1
    assert data["graduation_rate"] == pytest.approx(2 / 3, rel=1e-3)


# ---------------------------------------------------------------------------
# /billing/subscription
# ---------------------------------------------------------------------------


def test_get_subscription_no_workspace(client, mock_supabase):
    mock_supabase.add_response("workspaces", "select", [])

    resp = client.get("/api/v1/billing/subscription", headers=_jwt_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["plan"] is None


def test_get_subscription_with_workspace(client, mock_supabase):
    mock_supabase.add_response(
        "workspaces",
        "select",
        [
            {
                "id": "ws-1",
                "owner_id": "user-1",
                "plan": "pro",
                "subscription_status": "active",
                "subscription_period_end": None,
            }
        ],
    )
    mock_supabase.add_response("brains", "select", [{"id": "brain-1", "user_id": "user-1"}])
    mock_supabase.add_response(
        "lessons",
        "select",
        [{"id": "l1", "brain_id": "brain-1"}, {"id": "l2", "brain_id": "brain-1"}],
    )
    mock_supabase.add_response("events", "select", [{"id": "e1", "brain_id": "brain-1"}])

    resp = client.get("/api/v1/billing/subscription", headers=_jwt_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["plan"] == "pro"
    assert data["status"] == "active"
    assert data["usage"]["brains"] == 1
    assert data["usage"]["lessons"] == 2
