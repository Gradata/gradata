"""Tests for team / workspace-member endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_user_id
from app.main import create_app


CALLER_USER_ID = "user-caller"
OWNER_USER_ID = "user-owner"
ADMIN_USER_ID = "user-admin"
MEMBER_USER_ID = "user-member"
OUTSIDER_USER_ID = "user-outsider"
WORKSPACE_ID = "ws-1"


@pytest.fixture
def app_with_user(monkeypatch):
    """Create a fresh FastAPI app with get_current_user_id overridable."""

    def _build(stub_user: str):
        app = create_app()
        app.dependency_overrides[get_current_user_id] = lambda: stub_user
        return app

    return _build


@pytest.fixture
def stub_user(app_with_user, mock_supabase):
    """Helper: build (client, mock_supabase) authed as the given user_id."""

    def _setup(user_id: str = CALLER_USER_ID, *, members: list[dict] | None = None,
               brains: list[dict] | None = None) -> TestClient:
        app = app_with_user(user_id)
        if members is not None:
            mock_supabase.add_response("workspace_members", "select", members)
        if brains is not None:
            mock_supabase.add_response("brains", "select", brains)
        return TestClient(app)

    return _setup


# ---------------------------------------------------------------------------
# GET /workspaces/{ws}/members
# ---------------------------------------------------------------------------


def test_list_members_returns_list_for_workspace_member(stub_user, mock_supabase):
    members = [
        {
            "workspace_id": WORKSPACE_ID,
            "user_id": OWNER_USER_ID,
            "role": "owner",
            "joined_at": "2026-01-01T00:00:00+00:00",
            "email": "owner@example.com",
            "display_name": "Owner",
        },
        {
            "workspace_id": WORKSPACE_ID,
            "user_id": CALLER_USER_ID,
            "role": "admin",
            "joined_at": "2026-01-02T00:00:00+00:00",
            "email": "caller@example.com",
            "display_name": "Caller",
        },
    ]
    brains = [
        {
            "id": "brain-1",
            "workspace_id": WORKSPACE_ID,
            "user_id": OWNER_USER_ID,
            "last_sync_at": "2026-04-10T00:00:00+00:00",
        },
        {
            "id": "brain-2",
            "workspace_id": WORKSPACE_ID,
            "user_id": OWNER_USER_ID,
            "last_sync_at": "2026-04-11T00:00:00+00:00",  # newer
        },
    ]
    client = stub_user(CALLER_USER_ID, members=members, brains=brains)

    resp = client.get(f"/api/v1/workspaces/{WORKSPACE_ID}/members")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    by_id = {m["user_id"]: m for m in body}
    assert by_id[OWNER_USER_ID]["role"] == "owner"
    assert by_id[OWNER_USER_ID]["last_sync_at"] == "2026-04-11T00:00:00+00:00"
    assert by_id[CALLER_USER_ID]["last_sync_at"] is None  # no brains for caller


def test_list_members_403_for_non_member(stub_user, mock_supabase):
    members = [
        {"workspace_id": WORKSPACE_ID, "user_id": OWNER_USER_ID, "role": "owner"},
    ]
    client = stub_user(OUTSIDER_USER_ID, members=members)

    resp = client.get(f"/api/v1/workspaces/{WORKSPACE_ID}/members")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /workspaces/{ws}/invites
# ---------------------------------------------------------------------------


def test_create_invite_as_owner_returns_token_and_url(stub_user, mock_supabase):
    members = [
        {"workspace_id": WORKSPACE_ID, "user_id": CALLER_USER_ID, "role": "owner"},
    ]
    client = stub_user(CALLER_USER_ID, members=members)

    resp = client.post(
        f"/api/v1/workspaces/{WORKSPACE_ID}/invites",
        json={"email": "newbie@example.com", "role": "member"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "newbie@example.com"
    assert body["role"] == "member"
    assert body["token"]
    assert body["accept_url"].startswith("https://app.gradata.ai/invites/")
    assert body["accept_url"].endswith(body["token"])
    # Verify the insert hit the workspace_invites table.
    invited_emails = [
        r["email"] for r in mock_supabase._inserts if r.get("email") == "newbie@example.com"
    ]
    assert invited_emails


def test_create_invite_403_for_member_role(stub_user, mock_supabase):
    members = [
        {"workspace_id": WORKSPACE_ID, "user_id": CALLER_USER_ID, "role": "member"},
    ]
    client = stub_user(CALLER_USER_ID, members=members)

    resp = client.post(
        f"/api/v1/workspaces/{WORKSPACE_ID}/invites",
        json={"email": "newbie@example.com", "role": "member"},
    )
    assert resp.status_code == 403


def test_create_invite_validates_email_format(stub_user, mock_supabase):
    members = [
        {"workspace_id": WORKSPACE_ID, "user_id": CALLER_USER_ID, "role": "owner"},
    ]
    client = stub_user(CALLER_USER_ID, members=members)

    resp = client.post(
        f"/api/v1/workspaces/{WORKSPACE_ID}/invites",
        json={"email": "not-an-email", "role": "member"},
    )
    assert resp.status_code == 422  # pydantic validation error


# ---------------------------------------------------------------------------
# DELETE /workspaces/{ws}/members/{user_id}
# ---------------------------------------------------------------------------


def test_remove_member_403_for_member_role(stub_user, mock_supabase):
    members = [
        {"workspace_id": WORKSPACE_ID, "user_id": CALLER_USER_ID, "role": "member"},
        {"workspace_id": WORKSPACE_ID, "user_id": MEMBER_USER_ID, "role": "member"},
    ]
    client = stub_user(CALLER_USER_ID, members=members)

    resp = client.delete(
        f"/api/v1/workspaces/{WORKSPACE_ID}/members/{MEMBER_USER_ID}"
    )
    assert resp.status_code == 403


def test_remove_member_400_when_target_is_owner(stub_user, mock_supabase):
    members = [
        {"workspace_id": WORKSPACE_ID, "user_id": CALLER_USER_ID, "role": "admin"},
        {"workspace_id": WORKSPACE_ID, "user_id": OWNER_USER_ID, "role": "owner"},
    ]
    client = stub_user(CALLER_USER_ID, members=members)

    resp = client.delete(
        f"/api/v1/workspaces/{WORKSPACE_ID}/members/{OWNER_USER_ID}"
    )
    assert resp.status_code == 400
    assert "owner" in resp.json()["detail"].lower()


def test_remove_member_happy_path_as_admin(stub_user, mock_supabase):
    members = [
        {"workspace_id": WORKSPACE_ID, "user_id": CALLER_USER_ID, "role": "admin"},
        {"workspace_id": WORKSPACE_ID, "user_id": MEMBER_USER_ID, "role": "member"},
    ]
    client = stub_user(CALLER_USER_ID, members=members)

    resp = client.delete(
        f"/api/v1/workspaces/{WORKSPACE_ID}/members/{MEMBER_USER_ID}"
    )
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# PATCH /workspaces/{ws}/members/{user_id}
# ---------------------------------------------------------------------------


def test_update_role_400_when_setting_owner(stub_user, mock_supabase):
    members = [
        {"workspace_id": WORKSPACE_ID, "user_id": CALLER_USER_ID, "role": "admin"},
        {"workspace_id": WORKSPACE_ID, "user_id": MEMBER_USER_ID, "role": "member"},
    ]
    client = stub_user(CALLER_USER_ID, members=members)

    resp = client.patch(
        f"/api/v1/workspaces/{WORKSPACE_ID}/members/{MEMBER_USER_ID}",
        json={"role": "owner"},
    )
    # pydantic enum rejects 'owner' before our handler runs => 422.
    # If the model ever loosens to a plain str, our handler returns 400.
    assert resp.status_code in (400, 422)


def test_update_role_happy_path_as_admin(stub_user, mock_supabase):
    members = [
        {"workspace_id": WORKSPACE_ID, "user_id": CALLER_USER_ID, "role": "admin"},
        {
            "workspace_id": WORKSPACE_ID,
            "user_id": MEMBER_USER_ID,
            "role": "member",
            "email": "m@example.com",
            "display_name": "Member",
            "joined_at": "2026-01-03T00:00:00+00:00",
        },
    ]
    client = stub_user(CALLER_USER_ID, members=members)

    resp = client.patch(
        f"/api/v1/workspaces/{WORKSPACE_ID}/members/{MEMBER_USER_ID}",
        json={"role": "admin"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == MEMBER_USER_ID
    assert body["role"] == "admin"


def test_update_role_400_when_target_is_owner(stub_user, mock_supabase):
    members = [
        {"workspace_id": WORKSPACE_ID, "user_id": CALLER_USER_ID, "role": "admin"},
        {"workspace_id": WORKSPACE_ID, "user_id": OWNER_USER_ID, "role": "owner"},
    ]
    client = stub_user(CALLER_USER_ID, members=members)

    resp = client.patch(
        f"/api/v1/workspaces/{WORKSPACE_ID}/members/{OWNER_USER_ID}",
        json={"role": "admin"},
    )
    assert resp.status_code == 400
