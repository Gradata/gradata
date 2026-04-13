"""Tests for /health (liveness) and /ready (readiness) endpoints."""
from __future__ import annotations


def test_health_liveness_returns_minimal_payload(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["service"] == "gradata-cloud"
    assert "version" in body
    # Liveness must NOT include DB / uptime / env — those are readiness fields
    assert "db" not in body
    assert "uptime_seconds" not in body


def test_ready_returns_ready_when_db_ok(client, mock_supabase):
    """Happy path — DB ping succeeds, status is 'ready'."""
    # mock_supabase.select returns [] for unknown filters — no error raised
    resp = client.get("/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["db"] == "ok"
    assert isinstance(body["db_latency_ms"], (int, float))
    assert body["uptime_seconds"] >= 0
    assert body["environment"] == "test"
    assert "release" in body


def test_ready_returns_unavailable_when_db_fails(client, mock_supabase, monkeypatch):
    """Sad path — DB raises, status is 'unavailable'."""
    async def _explode(*_a, **_kw):
        raise RuntimeError("simulated DB outage")

    monkeypatch.setattr(mock_supabase, "select", _explode)
    resp = client.get("/ready")
    assert resp.status_code == 200  # The endpoint still responds; status field tells the truth
    body = resp.json()
    assert body["status"] == "unavailable"
    assert body["db"] == "fail"
    assert body["db_latency_ms"] is None


def test_ready_includes_release_from_env(client, mock_supabase, monkeypatch):
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "abc1234deadbeef")
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json()["release"] == "abc1234"
