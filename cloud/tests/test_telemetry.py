"""Tests for POST /telemetry/event — anonymous, rate-limited activation
event ingestion."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from app.routes import telemetry as tele


def _valid_body(event: str = "brain_initialized", **overrides) -> dict:
    """Minimal valid payload matching the SDK's wire format."""
    body = {
        "event": event,
        "user_id": hashlib.sha256(b"machine-id").hexdigest(),
        "ts": datetime.now(timezone.utc).isoformat(),
        "sdk_version": "0.5.0",
    }
    body.update(overrides)
    return body


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    """Clear the sliding-window rate limiter between tests."""
    tele._reset_rate_limiter()
    yield
    tele._reset_rate_limiter()


# ── Happy path ────────────────────────────────────────────────────────
class TestHappyPath:
    def test_accepts_valid_event(self, client, mock_supabase):
        resp = client.post("/telemetry/event", json=_valid_body())
        assert resp.status_code == 202
        assert resp.json() == {"status": "accepted"}

    def test_writes_to_db(self, client, mock_supabase):
        client.post("/telemetry/event", json=_valid_body("first_correction_captured"))
        assert len(mock_supabase._inserts) == 1
        row = mock_supabase._inserts[0]
        assert row["event"] == "first_correction_captured"
        assert row["sdk_version"] == "0.5.0"
        assert len(row["user_id"]) == 64

    def test_accepts_all_four_events(self, client, mock_supabase):
        for event in (
            "brain_initialized",
            "first_correction_captured",
            "first_graduation",
            "first_hook_installed",
        ):
            resp = client.post("/telemetry/event", json=_valid_body(event))
            assert resp.status_code == 202
        assert len(mock_supabase._inserts) == 4


# ── Schema validation — everything returns 202, invalid rows dropped ──
class TestSchema:
    def test_drops_unknown_event(self, client, mock_supabase):
        resp = client.post("/telemetry/event", json=_valid_body("mining_bitcoin"))
        assert resp.status_code == 202
        assert mock_supabase._inserts == []

    def test_drops_non_hex_user_id(self, client, mock_supabase):
        resp = client.post(
            "/telemetry/event",
            json=_valid_body(user_id="Z" * 64),
        )
        assert resp.status_code == 202
        assert mock_supabase._inserts == []

    def test_drops_wrong_length_user_id(self, client, mock_supabase):
        resp = client.post(
            "/telemetry/event",
            json=_valid_body(user_id="abc123"),
        )
        assert resp.status_code == 202
        assert mock_supabase._inserts == []

    def test_drops_extra_fields_silently(self, client, mock_supabase):
        """Extra fields are ignored by pydantic (default), so the insert
        still succeeds — but only the known fields get written."""
        body = _valid_body()
        body["email"] = "attacker@evil.com"
        body["lesson_text"] = "secret correction content"
        resp = client.post("/telemetry/event", json=body)
        assert resp.status_code == 202
        row = mock_supabase._inserts[0]
        assert "email" not in row
        assert "lesson_text" not in row

    def test_drops_malformed_json(self, client, mock_supabase):
        resp = client.post(
            "/telemetry/event",
            data=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 202
        assert mock_supabase._inserts == []

    def test_drops_non_object_body(self, client, mock_supabase):
        resp = client.post("/telemetry/event", json=["array", "not", "object"])
        assert resp.status_code == 202
        assert mock_supabase._inserts == []

    def test_drops_missing_fields(self, client, mock_supabase):
        resp = client.post("/telemetry/event", json={"event": "brain_initialized"})
        assert resp.status_code == 202
        assert mock_supabase._inserts == []


# ── Replay protection ────────────────────────────────────────────────
class TestReplay:
    def test_drops_old_events(self, client, mock_supabase):
        old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        resp = client.post("/telemetry/event", json=_valid_body(ts=old))
        assert resp.status_code == 202
        assert mock_supabase._inserts == []

    def test_drops_exactly_one_hour_old(self, client, mock_supabase):
        old = (datetime.now(timezone.utc) - timedelta(hours=1, seconds=5)).isoformat()
        resp = client.post("/telemetry/event", json=_valid_body(ts=old))
        assert resp.status_code == 202
        assert mock_supabase._inserts == []

    def test_accepts_recent_events(self, client, mock_supabase):
        recent = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        resp = client.post("/telemetry/event", json=_valid_body(ts=recent))
        assert resp.status_code == 202
        assert len(mock_supabase._inserts) == 1

    def test_drops_far_future_events(self, client, mock_supabase):
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        resp = client.post("/telemetry/event", json=_valid_body(ts=future))
        assert resp.status_code == 202
        assert mock_supabase._inserts == []

    def test_drops_naive_timestamps(self, client, mock_supabase):
        """Naive (no-tz) timestamps are not a valid SDK payload — reject at
        the API boundary (defense-in-depth) so a malicious client can't
        extend the replay window by picking a favourable local tz."""
        naive = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        assert "+" not in naive and not naive.endswith("Z")  # confirm naive
        resp = client.post("/telemetry/event", json=_valid_body(ts=naive))
        assert resp.status_code == 202
        assert mock_supabase._inserts == []


# ── Rate limiting ────────────────────────────────────────────────────
class TestRateLimit:
    def test_under_limit_accepts(self, client, mock_supabase):
        for _ in range(50):
            resp = client.post("/telemetry/event", json=_valid_body())
            assert resp.status_code == 202
        assert len(mock_supabase._inserts) == 50

    def test_over_limit_silently_drops(self, client, mock_supabase):
        # Send 120 and confirm only 100 hit the DB — all return 202.
        statuses = []
        for _ in range(120):
            resp = client.post("/telemetry/event", json=_valid_body())
            statuses.append(resp.status_code)
        assert all(s == 202 for s in statuses)
        assert len(mock_supabase._inserts) == tele.RATE_LIMIT

    def test_sliding_window_unit(self):
        """Verify the in-memory limiter math directly."""
        import time as real_time

        now = real_time.monotonic()
        # 100 hits in the window — all allowed
        for i in range(tele.RATE_LIMIT):
            assert tele._allow("1.2.3.4", now=now + i * 0.01) is True
        # 101st denied
        assert tele._allow("1.2.3.4", now=now + 1.0) is False
        # After the window slides forward, allowed again
        assert tele._allow("1.2.3.4", now=now + tele.RATE_WINDOW + 1) is True


# ── DB errors never leak ─────────────────────────────────────────────
class TestErrorHandling:
    def test_db_exception_still_returns_202(self, client, mock_supabase, monkeypatch):
        async def _boom(*_a, **_kw):
            raise RuntimeError("db down")

        monkeypatch.setattr(mock_supabase, "insert", _boom)
        resp = client.post("/telemetry/event", json=_valid_body())
        assert resp.status_code == 202


# ── No auth required ─────────────────────────────────────────────────
class TestPublic:
    def test_no_auth_header_still_works(self, client, mock_supabase):
        # No Authorization header at all
        resp = client.post("/telemetry/event", json=_valid_body())
        assert resp.status_code == 202
        assert len(mock_supabase._inserts) == 1
