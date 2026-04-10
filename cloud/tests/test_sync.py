"""Tests for POST /api/v1/sync endpoint."""
from __future__ import annotations

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
