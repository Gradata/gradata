"""Tests for brain registration endpoints."""
from __future__ import annotations

import pytest


def test_register_brain(client, mock_supabase, auth_headers):
    """POST /api/v1/brains/connect registers a brain."""
    mock_supabase.add_response(
        "brains", "select",
        [{"id": "brain-1", "workspace_id": "ws-1", "user_id": "user-1", "api_key": "gd_TVAL"}],
    )
    resp = client.post(
        "/api/v1/brains/connect",
        json={"brain_name": "my-brain", "domain": "sales"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["brain_id"] == "brain-1"
    assert data["status"] == "connected"


def test_list_brains(client, mock_supabase, auth_headers):
    """GET /api/v1/brains returns brains for authenticated user."""
    mock_supabase.add_response(
        "brains", "select",
        [
            {"id": "brain-1", "workspace_id": "ws-1", "user_id": "user-1", "api_key": "gd_TVAL", "name": "default"},
            {"id": "brain-2", "workspace_id": "ws-1", "user_id": "user-1", "api_key": "gd_TVA2", "name": "sales"},
        ],
    )
    resp = client.get("/api/v1/brains", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2
