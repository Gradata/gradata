"""Tests for meta-rules, activity, and rule-patches endpoints."""
from __future__ import annotations

import pytest


@pytest.fixture
def valid_bearer_patches(client):
    """Override ``get_brain_for_request`` to return a stub brain for any request.

    Avoids threading Supabase + API key validation through every test.
    """
    from app.auth import get_brain_for_request

    async def _stub_get_brain(brain_id: str = "brain-1"):
        return {"id": brain_id, "user_id": "u1", "name": "test"}

    client.app.dependency_overrides[get_brain_for_request] = _stub_get_brain
    yield
    client.app.dependency_overrides.pop(get_brain_for_request, None)


class TestMetaRulesEndpoint:
    def test_returns_empty_list_when_none(self, client, mock_supabase, auth_headers, valid_bearer_patches):
        mock_supabase.add_response("meta_rules", "select", [])
        resp = client.get("/api/v1/brains/brain-1/meta-rules", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_meta_rules_newest_first(self, client, mock_supabase, auth_headers, valid_bearer_patches):
        mock_supabase.add_response("meta_rules", "select", [
            {"id": "m1", "brain_id": "brain-1", "title": "older",
             "description": "", "source_lesson_ids": ["l1", "l2", "l3"],
             "created_at": "2026-04-01T00:00:00Z"},
            {"id": "m2", "brain_id": "brain-1", "title": "newer",
             "description": "", "source_lesson_ids": ["l4", "l5", "l6"],
             "created_at": "2026-04-12T00:00:00Z"},
        ])
        resp = client.get("/api/v1/brains/brain-1/meta-rules", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["id"] == "m2"  # newer first
        assert data[1]["id"] == "m1"

    def test_pagination(self, client, mock_supabase, auth_headers, valid_bearer_patches):
        mock_supabase.add_response("meta_rules", "select", [
            {"id": f"m{i}", "brain_id": "brain-1", "title": f"rule {i}",
             "description": "", "source_lesson_ids": [],
             "created_at": f"2026-04-{i:02d}T00:00:00Z"} for i in range(1, 11)
        ])
        resp = client.get(
            "/api/v1/brains/brain-1/meta-rules?limit=3&offset=0", headers=auth_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 3


class TestActivityEndpoint:
    def test_filters_to_visible_types_only(self, client, mock_supabase, auth_headers, valid_bearer_patches):
        mock_supabase.add_response("events", "select", [
            {"id": "e1", "brain_id": "brain-1", "type": "correction_logged",
             "source": "", "data": {}, "tags": [], "session": 1,
             "created_at": "2026-04-12T10:00:00Z"},
            {"id": "e2", "brain_id": "brain-1", "type": "graduation",
             "source": "", "data": {"title": "rule1"}, "tags": [], "session": 1,
             "created_at": "2026-04-12T11:00:00Z"},
            {"id": "e3", "brain_id": "brain-1", "type": "internal_debug",
             "source": "", "data": {}, "tags": [], "session": 1,
             "created_at": "2026-04-12T12:00:00Z"},
        ])
        resp = client.get("/api/v1/brains/brain-1/activity", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        # Only "graduation" is in _VISIBLE_EVENT_TYPES
        assert len(data) == 1
        assert data[0]["type"] == "graduation"

    def test_returns_empty_when_no_events(self, client, mock_supabase, auth_headers, valid_bearer_patches):
        mock_supabase.add_response("events", "select", [])
        resp = client.get("/api/v1/brains/brain-1/activity", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []


class TestRulePatchesEndpoint:
    def test_returns_empty_when_no_lessons(self, client, mock_supabase, auth_headers, valid_bearer_patches):
        mock_supabase.add_response("lessons", "select", [])
        resp = client.get("/api/v1/brains/brain-1/rule-patches", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_patches_for_brains_lessons_only(self, client, mock_supabase, auth_headers, valid_bearer_patches):
        mock_supabase.add_response("lessons", "select", [
            {"id": "lesson-mine-1", "brain_id": "brain-1"},
            {"id": "lesson-mine-2", "brain_id": "brain-1"},
        ])
        mock_supabase.add_response("rule_patches", "select", [
            {"id": "p1", "lesson_id": "lesson-mine-1",
             "old_description": "A", "new_description": "B", "reason": "test",
             "created_at": "2026-04-12T10:00:00Z"},
            {"id": "p2", "lesson_id": "someone-elses-lesson",
             "old_description": "X", "new_description": "Y", "reason": "other",
             "created_at": "2026-04-12T11:00:00Z"},
            {"id": "p3", "lesson_id": "lesson-mine-2",
             "old_description": "C", "new_description": "D", "reason": "mine",
             "created_at": "2026-04-12T12:00:00Z"},
        ])
        resp = client.get("/api/v1/brains/brain-1/rule-patches", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert {p["id"] for p in data} == {"p1", "p3"}  # not p2
        # Sorted newest first
        assert data[0]["id"] == "p3"

    def test_rollback_creates_inverse_patch_and_updates_lesson(
        self, client, mock_supabase, auth_headers, valid_bearer_patches,
    ):
        mock_supabase.add_response("rule_patches", "select", [
            {"id": "p1", "lesson_id": "lesson-1",
             "old_description": "original", "new_description": "evolved",
             "reason": "auto"},
        ])
        mock_supabase.add_response("lessons", "select", [
            {"id": "lesson-1", "brain_id": "brain-1"},
        ])
        resp = client.post(
            "/api/v1/brains/brain-1/rule-patches/p1/rollback", headers=auth_headers,
        )
        assert resp.status_code == 204
        # Verify inverse patch was inserted + lesson was updated
        inserts = mock_supabase._inserts
        assert any(
            r.get("lesson_id") == "lesson-1"
            and r.get("old_description") == "evolved"
            and r.get("new_description") == "original"
            for r in inserts
        )

    def test_rollback_rejects_patch_from_other_brain(
        self, client, mock_supabase, auth_headers, valid_bearer_patches,
    ):
        mock_supabase.add_response("rule_patches", "select", [
            {"id": "p1", "lesson_id": "lesson-elsewhere",
             "old_description": "x", "new_description": "y", "reason": ""},
        ])
        mock_supabase.add_response("lessons", "select", [
            {"id": "lesson-elsewhere", "brain_id": "different-brain"},
        ])
        resp = client.post(
            "/api/v1/brains/brain-1/rule-patches/p1/rollback", headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_rollback_returns_404_when_patch_missing(
        self, client, mock_supabase, auth_headers, valid_bearer_patches,
    ):
        mock_supabase.add_response("rule_patches", "select", [])
        resp = client.post(
            "/api/v1/brains/brain-1/rule-patches/missing/rollback", headers=auth_headers,
        )
        assert resp.status_code == 404
