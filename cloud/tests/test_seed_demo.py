"""Tests for demo seed data: migration shape + POST /brains/{id}/clear-demo."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from jose import jwt


_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "migrations"
    / "004_seed_demo_brain.sql"
)

_JWT_KEY = os.environ.get("GRADATA_SUPABASE_JWT_KEY", "test-only-hmac-not-a-real-credential-x")


def _make_jwt(user_id: str = "user-1") -> str:
    return jwt.encode({"sub": user_id}, _JWT_KEY, algorithm="HS256")


def _jwt_headers(user_id: str = "user-1") -> dict:
    return {"Authorization": f"Bearer {_make_jwt(user_id)}"}


# ---------------------------------------------------------------------------
# Migration shape
# ---------------------------------------------------------------------------


def test_migration_file_exists_and_has_seed_function():
    """Migration 004 must define seed_demo_brain and tag rows with is_demo."""
    assert _MIGRATION_PATH.exists(), "migrations/004_seed_demo_brain.sql missing"
    sql = _MIGRATION_PATH.read_text(encoding="utf-8")

    # Core function signature present
    assert re.search(
        r"CREATE\s+OR\s+REPLACE\s+FUNCTION\s+seed_demo_brain\s*\(",
        sql,
        flags=re.IGNORECASE,
    ), "seed_demo_brain function signature not found"

    # Rows get the is_demo marker
    assert "is_demo" in sql, "is_demo marker missing from migration"

    # Trigger function replaced to call seed_demo_brain
    assert "PERFORM seed_demo_brain" in sql, "handle_new_user should PERFORM seed_demo_brain"

    # Expected row counts referenced in comments / structure
    # 6-dim taxonomy dimensions
    for dim in (
        "Goal Alignment",
        "Tone & Register",
        "Clarity & Structure",
        "Factual Integrity",
        "Domain Fit",
        "Actionability",
    ):
        assert dim in sql, f"dimension {dim!r} missing from seed"

    # Uses jsonb_build_object per task constraint
    assert "jsonb_build_object" in sql


# ---------------------------------------------------------------------------
# POST /brains/{brain_id}/clear-demo
# ---------------------------------------------------------------------------


def test_clear_demo_happy_path(client, mock_supabase, auth_headers):
    """Deletes rows flagged is_demo=true across child tables + the brain row itself."""
    # Brain with demo metadata, owned via API key
    mock_supabase.add_response(
        "brains",
        "select",
        [
            {
                "id": "brain-1",
                "user_id": "user-1",
                "api_key": "gd_TVAL",
                "metadata": {"is_demo": True},
            }
        ],
    )
    # Child rows — mix of demo and non-demo so we confirm filtering
    mock_supabase.add_response(
        "corrections",
        "select",
        [
            {"id": "c1", "brain_id": "brain-1", "data": {"is_demo": True}},
            {"id": "c2", "brain_id": "brain-1", "data": {"is_demo": True}},
            {"id": "c3", "brain_id": "brain-1", "data": {}},  # non-demo, skip
        ],
    )
    mock_supabase.add_response(
        "lessons",
        "select",
        [
            {"id": "l1", "brain_id": "brain-1", "data": {"is_demo": True}},
            {"id": "l2", "brain_id": "brain-1", "data": {"is_demo": True}},
        ],
    )
    mock_supabase.add_response(
        "meta_rules",
        "select",
        [{"id": "m1", "brain_id": "brain-1", "data": {"is_demo": True}}],
    )
    mock_supabase.add_response(
        "events",
        "select",
        [
            {"id": "e1", "brain_id": "brain-1", "data": {"is_demo": True}},
            {"id": "e2", "brain_id": "brain-1", "data": {"is_demo": True}},
            {"id": "e3", "brain_id": "brain-1", "data": {"is_demo": True}},
        ],
    )

    resp = client.post("/api/v1/brains/brain-1/clear-demo", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    # 2 corrections + 2 lessons + 1 meta_rule + 3 events + 1 brain = 9
    assert body["deleted"] == 9
    assert body["by_table"]["corrections"] == 2
    assert body["by_table"]["lessons"] == 2
    assert body["by_table"]["meta_rules"] == 1
    assert body["by_table"]["events"] == 3
    assert body["by_table"]["brains"] == 1


def test_clear_demo_zero_when_no_demo_rows(client, mock_supabase, auth_headers):
    """Returns 0 when no rows are flagged is_demo."""
    mock_supabase.add_response(
        "brains",
        "select",
        [
            {
                "id": "brain-1",
                "user_id": "user-1",
                "api_key": "gd_TVAL",
                "metadata": {},  # not a demo brain
            }
        ],
    )
    mock_supabase.add_response("corrections", "select", [
        {"id": "c1", "brain_id": "brain-1", "data": {}},
    ])
    mock_supabase.add_response("lessons", "select", [])
    mock_supabase.add_response("meta_rules", "select", [])
    mock_supabase.add_response("events", "select", [])

    resp = client.post("/api/v1/brains/brain-1/clear-demo", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["deleted"] == 0
    assert body["by_table"]["corrections"] == 0
    assert body["by_table"]["brains"] == 0


def test_clear_demo_forbidden_if_not_owner(client, mock_supabase):
    """JWT auth: user-2 cannot clear brain owned by user-1 -> 403."""
    mock_supabase.add_response(
        "brains",
        "select",
        [{"id": "brain-1", "user_id": "user-1", "api_key": "gd_TVAL"}],
    )

    resp = client.post(
        "/api/v1/brains/brain-1/clear-demo",
        headers=_jwt_headers("user-2"),
    )
    assert resp.status_code == 403


def test_clear_demo_not_found(client, mock_supabase):
    """Unknown brain -> 404 via JWT auth path."""
    mock_supabase.add_response("brains", "select", [])

    resp = client.post(
        "/api/v1/brains/missing/clear-demo",
        headers=_jwt_headers(),
    )
    assert resp.status_code == 404


def test_clear_demo_api_key_wrong_brain(client, mock_supabase, auth_headers):
    """API key auth: key scoped to brain-1 cannot clear brain-other -> 403."""
    mock_supabase.add_response(
        "brains",
        "select",
        [{"id": "brain-1", "user_id": "user-1", "api_key": "gd_TVAL"}],
    )

    resp = client.post("/api/v1/brains/brain-other/clear-demo", headers=auth_headers)
    assert resp.status_code == 403


def test_clear_demo_preserves_non_demo_brain_row(client, mock_supabase, auth_headers):
    """Even when demo children exist, a non-demo brain row is NOT deleted."""
    mock_supabase.add_response(
        "brains",
        "select",
        [
            {
                "id": "brain-1",
                "user_id": "user-1",
                "api_key": "gd_TVAL",
                "metadata": {},  # real brain
            }
        ],
    )
    mock_supabase.add_response(
        "corrections",
        "select",
        [{"id": "c1", "brain_id": "brain-1", "data": {"is_demo": True}}],
    )
    mock_supabase.add_response("lessons", "select", [])
    mock_supabase.add_response("meta_rules", "select", [])
    mock_supabase.add_response("events", "select", [])

    resp = client.post("/api/v1/brains/brain-1/clear-demo", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["by_table"]["brains"] == 0
    assert body["by_table"]["corrections"] == 1
    assert body["deleted"] == 1
