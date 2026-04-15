"""Tests for POST /api/v1/sync endpoint."""
from __future__ import annotations

import logging

import pytest


def test_sync_empty_payload(client, mock_supabase, auth_headers):
    """Sync with no data succeeds with zero counts."""
    mock_supabase.add_response(
        "brains", "select",
        [{"id": "brain-1", "workspace_id": "ws-1", "user_id": "user-1", "api_key": "gd_TVAL"}],
    )
    resp = client.post(
        "/api/v1/sync",
        json={"brain_name": "default", "corrections": [], "lessons": [], "events": []},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["corrections_synced"] == 0


def test_sync_with_corrections(client, mock_supabase, auth_headers):
    """Sync with corrections inserts them."""
    mock_supabase.add_response(
        "brains", "select",
        [{"id": "brain-1", "workspace_id": "ws-1", "user_id": "user-1", "api_key": "gd_TVAL"}],
    )
    resp = client.post(
        "/api/v1/sync",
        json={
            "brain_name": "default",
            "corrections": [
                {
                    "session": 1,
                    "category": "TONE",
                    "severity": "minor",
                    "description": "Too formal",
                    "draft_preview": "Dear Sir,",
                    "final_preview": "Hey,",
                }
            ],
            "lessons": [],
            "events": [],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["corrections_synced"] == 1
    assert len(mock_supabase._inserts) == 1
    assert mock_supabase._inserts[0]["category"] == "TONE"


def test_sync_with_lessons(client, mock_supabase, auth_headers):
    """Sync with lessons upserts them."""
    mock_supabase.add_response(
        "brains", "select",
        [{"id": "brain-1", "workspace_id": "ws-1", "user_id": "user-1", "api_key": "gd_TVAL"}],
    )
    resp = client.post(
        "/api/v1/sync",
        json={
            "brain_name": "default",
            "corrections": [],
            "lessons": [
                {
                    "category": "TONE",
                    "description": "Use casual tone in emails",
                    "state": "RULE",
                    "confidence": 0.92,
                    "fire_count": 15,
                }
            ],
            "events": [],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["lessons_synced"] == 1


def test_sync_unauthenticated(client):
    """Sync without auth is rejected (401 or 403)."""
    resp = client.post(
        "/api/v1/sync",
        json={"brain_name": "default", "corrections": [], "lessons": [], "events": []},
    )
    assert resp.status_code in (401, 403)


def test_sync_rule_patched_event_populates_rule_patches(client, mock_supabase, auth_headers):
    """RULE_PATCHED events in the events array write a matching rule_patches row."""
    mock_supabase.add_response(
        "brains", "select",
        [{"id": "brain-1", "workspace_id": "ws-1", "user_id": "user-1", "api_key": "gd_TVAL"}],
    )
    # Seed a lesson the event can resolve against
    mock_supabase.add_response(
        "lessons", "select",
        [{
            "id": "lesson-xyz",
            "brain_id": "brain-1",
            "category": "TONE",
            "description": "Keep tone casual and direct",
        }],
    )
    resp = client.post(
        "/api/v1/sync",
        json={
            "brain_name": "default",
            "corrections": [],
            "lessons": [],
            "events": [
                {
                    "type": "RULE_PATCHED",
                    "source": "brain.patch_rule",
                    "data": {
                        "category": "TONE",
                        "old_description": "Use casual tone in emails",
                        "new_description": "Keep tone casual and direct",
                        "reason": "self-healing: recurrence fix",
                    },
                    "tags": ["category:TONE", "self_healing"],
                    "session": 7,
                }
            ],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["events_synced"] == 1

    # The rule_patches insert should be present in mock._inserts
    rule_patch_inserts = [row for row in mock_supabase._inserts if "old_description" in row and "new_description" in row]
    assert len(rule_patch_inserts) == 1, f"expected 1 rule_patches row, got {len(rule_patch_inserts)}"
    patch = rule_patch_inserts[0]
    assert patch["lesson_id"] == "lesson-xyz"
    assert patch["old_description"] == "Use casual tone in emails"
    assert patch["new_description"] == "Keep tone casual and direct"
    assert "self-healing" in patch["reason"]


def test_sync_rule_patched_event_without_matching_lesson_is_skipped(client, mock_supabase, auth_headers):
    """A RULE_PATCHED event for a category with no lesson is dropped, not raised."""
    mock_supabase.add_response(
        "brains", "select",
        [{"id": "brain-1", "workspace_id": "ws-1", "user_id": "user-1", "api_key": "gd_TVAL"}],
    )
    # No lesson seeded for the category → the patch should be skipped
    resp = client.post(
        "/api/v1/sync",
        json={
            "brain_name": "default",
            "corrections": [],
            "lessons": [],
            "events": [
                {
                    "type": "RULE_PATCHED",
                    "source": "brain.patch_rule",
                    "data": {
                        "category": "GHOST_CATEGORY",
                        "old_description": "old",
                        "new_description": "new",
                    },
                    "tags": [],
                    "session": None,
                }
            ],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    # The event row itself still gets inserted — only the rule_patches side is skipped
    assert resp.json()["events_synced"] == 1
    rule_patch_inserts = [row for row in mock_supabase._inserts if "old_description" in row and "new_description" in row]
    assert rule_patch_inserts == []


def test_sync_rule_patched_malformed_payload_is_warned_and_skipped(
    client, mock_supabase, auth_headers, caplog
):
    """Malformed RULE_PATCHED events (missing required fields) are warned + skipped.

    Guards the telemetry observability path: we must log a warning and NOT
    insert a rule_patches row, even when *every* patched event is malformed
    (no lesson lookup happens because there's no valid category to query).
    """
    mock_supabase.add_response(
        "brains", "select",
        [{"id": "brain-1", "workspace_id": "ws-1", "user_id": "user-1", "api_key": "gd_TVAL"}],
    )

    with caplog.at_level(logging.WARNING, logger="app.routes.sync"):
        resp = client.post(
            "/api/v1/sync",
            json={
                "brain_name": "default",
                "corrections": [],
                "lessons": [],
                "events": [
                    # Missing category entirely
                    {
                        "type": "RULE_PATCHED",
                        "source": "brain.patch_rule",
                        "data": {
                            "old_description": "old",
                            "new_description": "new",
                        },
                        "tags": [],
                        "session": None,
                    },
                    # Missing old_description + new_description
                    {
                        "type": "RULE_PATCHED",
                        "source": "brain.patch_rule",
                        "data": {
                            "category": "TONE",
                            "reason": "self_healing",
                        },
                        "tags": [],
                        "session": None,
                    },
                    # Malformed type: category is an int (not a string).
                    # Must be treated as missing — no AttributeError, no insert.
                    {
                        "type": "RULE_PATCHED",
                        "source": "brain.patch_rule",
                        "data": {
                            "category": 123,
                            "old_description": "x",
                            "new_description": "y",
                        },
                        "tags": [],
                        "session": None,
                    },
                ],
            },
            headers=auth_headers,
        )

    assert resp.status_code == 200, resp.text
    # All three events still land in the events table — only the rule_patches side is skipped
    assert resp.json()["events_synced"] == 3

    # A warning must have been emitted for each malformed event
    warning_msgs = [
        r.getMessage() for r in caplog.records
        if r.levelno >= logging.WARNING and "rule-patches" in r.getMessage()
    ]
    assert len(warning_msgs) >= 3, f"expected >=3 warnings, got {warning_msgs}"
    assert any("missing category" in m for m in warning_msgs)
    assert any(
        "old_description" in m and "new_description" in m for m in warning_msgs
    )

    # No rule_patches insert should have been attempted
    rule_patch_inserts = [
        row for row in mock_supabase._inserts
        if "old_description" in row and "new_description" in row
    ]
    assert rule_patch_inserts == []


def test_sync_invalid_payload(client, mock_supabase, auth_headers):
    """Invalid payload returns 422."""
    mock_supabase.add_response(
        "brains", "select",
        [{"id": "brain-1", "workspace_id": "ws-1", "user_id": "user-1", "api_key": "gd_TVAL"}],
    )
    resp = client.post(
        "/api/v1/sync",
        json={"corrections": [{"severity": "catastrophic"}]},  # bad severity
        headers=auth_headers,
    )
    assert resp.status_code == 422
