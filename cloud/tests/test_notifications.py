"""Tests for /users/me/notifications GET + PUT."""
from __future__ import annotations

import pytest


@pytest.fixture
def stub_user(client):
    """Override the get_current_user_id Depends() with a fixed-id stub."""
    from app.auth import get_current_user_id

    async def _stub_user_id() -> str:
        return "test-user-1"

    client.app.dependency_overrides[get_current_user_id] = _stub_user_id
    yield "test-user-1"
    client.app.dependency_overrides.pop(get_current_user_id, None)


class TestGetNotifications:
    def test_returns_defaults_when_no_row(self, client, mock_supabase, auth_headers, stub_user):
        mock_supabase.add_response("workspace_members", "select", [])
        resp = client.get("/api/v1/users/me/notifications", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        # SIM16-validated defaults
        assert body["alert_correction_spike"] is True
        assert body["alert_rule_regression"] is True
        assert body["alert_meta_rule_emerged"] is False
        assert body["digest_cadence"] == "weekly"
        assert body["digest_email"] == ""
        assert body["slack_webhook"] == ""

    def test_returns_stored_prefs(self, client, mock_supabase, auth_headers, stub_user):
        mock_supabase.add_response("workspace_members", "select", [
            {"user_id": "test-user-1", "notification_prefs": {
                "alert_correction_spike": False,
                "alert_rule_regression": True,
                "alert_meta_rule_emerged": True,
                "digest_cadence": "daily",
                "digest_email": "alerts@example.com",
                "slack_webhook": "https://hooks.slack.com/services/x",
            }},
        ])
        resp = client.get("/api/v1/users/me/notifications", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["digest_cadence"] == "daily"
        assert body["digest_email"] == "alerts@example.com"
        assert body["alert_correction_spike"] is False

    def test_falls_back_to_defaults_when_prefs_blank(self, client, mock_supabase, auth_headers, stub_user):
        mock_supabase.add_response("workspace_members", "select", [{"user_id": "test-user-1", "notification_prefs": None}])
        resp = client.get("/api/v1/users/me/notifications", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["digest_cadence"] == "weekly"


class TestPutNotifications:
    def test_replaces_prefs_and_returns_them(self, client, mock_supabase, auth_headers, stub_user):
        payload = {
            "alert_correction_spike": False,
            "alert_rule_regression": False,
            "alert_meta_rule_emerged": True,
            "digest_cadence": "monthly",
            "digest_email": "",
            "slack_webhook": "",
        }
        resp = client.put("/api/v1/users/me/notifications", json=payload, headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["digest_cadence"] == "monthly"
        assert body["alert_meta_rule_emerged"] is True

    def test_rejects_invalid_cadence(self, client, mock_supabase, auth_headers, stub_user):
        payload = {"digest_cadence": "yearly"}
        resp = client.put("/api/v1/users/me/notifications", json=payload, headers=auth_headers)
        # Pydantic ValidationError → 422
        assert resp.status_code == 422

    def test_accepts_partial_payload_using_defaults(self, client, mock_supabase, auth_headers, stub_user):
        # Pydantic fills in defaults for omitted fields
        payload = {"digest_cadence": "off"}
        resp = client.put("/api/v1/users/me/notifications", json=payload, headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["digest_cadence"] == "off"
        # Defaults preserved
        assert body["alert_correction_spike"] is True
