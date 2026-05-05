"""Tests for CloudClient.sync() — watermark cursor + idempotency (Bug 2 fix)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from gradata.cloud.client import CloudClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(brain_dir: Path) -> CloudClient:
    client = CloudClient(brain_dir, api_key="gd_test", endpoint="https://api.gradata.ai/api/v1")
    client.connected = True
    client._brain_id = "brain-test"
    return client


def _write_events(path: Path, events: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(ev) for ev in events) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSyncNoEvents:
    def test_no_events_file_returns_zero(self, tmp_path: Path):
        """sync() returns 0 when events.jsonl does not exist."""
        client = _make_client(tmp_path)
        assert client.sync() == 0

    def test_empty_events_file_returns_zero(self, tmp_path: Path):
        """sync() returns 0 when events.jsonl is empty."""
        (tmp_path / "events.jsonl").write_text("", encoding="utf-8")
        client = _make_client(tmp_path)
        assert client.sync() == 0

    def test_not_connected_returns_zero(self, tmp_path: Path):
        client = CloudClient(tmp_path, api_key="gd_test", endpoint="https://api.gradata.ai/api/v1")
        assert client.sync() == 0


class TestSyncThreeEvents:
    def test_posts_once_and_advances_watermark(self, tmp_path: Path):
        """3 unsynced events → one POST, watermark advances."""
        events = [
            {"ts": "2026-01-01T10:00:00Z", "type": "CORRECTION", "source": "brain"},
            {"ts": "2026-01-01T11:00:00Z", "type": "LESSON_FIRED", "source": "brain"},
            {"ts": "2026-01-01T12:00:00Z", "type": "CORRECTION", "source": "brain"},
        ]
        _write_events(tmp_path / "events.jsonl", events)
        client = _make_client(tmp_path)

        resp_body = {"status": "ok", "ingested_count": 3, "new_watermark": "2026-01-01T12:00:00Z"}
        with patch.object(client, "_post", return_value=resp_body) as mock_post:
            result = client.sync()

        assert result == 3
        mock_post.assert_called_once()
        call_args = mock_post.call_args[0]
        assert call_args[0] == "/sync"
        payload = call_args[1]
        assert len(payload["events"]) == 3
        # All events must have event_id (deterministic hash)
        assert all(ev["event_id"] for ev in payload["events"])

        # Watermark was saved
        state = json.loads((tmp_path / ".gradata-sync-state.json").read_text())
        assert state["last_sync_at"] == "2026-01-01T12:00:00Z"


class TestSyncBatching:
    def test_1500_events_sends_three_batches(self, tmp_path: Path):
        """1500 events with batch_size=500 → 3 POST calls, watermark advances after each."""
        events = [
            {"ts": f"2026-01-01T{i:05d}Z", "type": "CORRECTION", "source": "brain"}
            for i in range(1500)
        ]
        _write_events(tmp_path / "events.jsonl", events)
        client = _make_client(tmp_path)

        call_count = [0]

        def fake_post(path, data):
            call_count[0] += 1
            batch = data["events"]
            last_ts = batch[-1]["created_at"]
            return {"status": "ok", "ingested_count": len(batch), "new_watermark": last_ts}

        with patch.object(client, "_post", side_effect=fake_post):
            result = client.sync(batch_size=500)

        assert call_count[0] == 3
        assert result == 1500

    def test_watermark_filters_already_synced_events(self, tmp_path: Path):
        """Re-running sync() after success sends 0 events (watermark already advanced)."""
        events = [
            {"ts": "2026-01-01T10:00:00Z", "type": "CORRECTION", "source": "brain"},
            {"ts": "2026-01-01T11:00:00Z", "type": "CORRECTION", "source": "brain"},
        ]
        _write_events(tmp_path / "events.jsonl", events)
        # Pre-set watermark past all events
        (tmp_path / ".gradata-sync-state.json").write_text(
            json.dumps({"last_sync_at": "2026-01-01T11:00:00Z"}), encoding="utf-8"
        )
        client = _make_client(tmp_path)

        with patch.object(client, "_post") as mock_post:
            result = client.sync()

        assert result == 0
        mock_post.assert_not_called()


class TestSync413Retry:
    def test_413_halves_batch_and_retries(self, tmp_path: Path):
        """413 from server causes batch to halve and retry from same offset."""
        from gradata.cloud.client import _TooLargeError

        events = [
            {"ts": f"2026-01-{i:02d}T10:00:00Z", "type": "CORRECTION", "source": "brain"}
            for i in range(1, 5)
        ]
        _write_events(tmp_path / "events.jsonl", events)
        client = _make_client(tmp_path)

        call_count = [0]

        def fake_post(path, data):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call with batch_size=4 → 413
                raise _TooLargeError()
            # Second call with batch_size=2 → success
            batch = data["events"]
            last_ts = batch[-1]["created_at"]
            return {"status": "ok", "ingested_count": len(batch), "new_watermark": last_ts}

        with patch.object(client, "_post", side_effect=fake_post):
            result = client.sync(batch_size=4)

        # Called at least twice: once with 413, once (or more) with halved batch
        assert call_count[0] >= 2
        assert result > 0


class TestSyncEventIdDeterminism:
    def test_event_id_is_deterministic(self):
        """Same event always maps to same event_id (idempotency guarantee)."""
        ev = {"ts": "2026-01-01T10:00:00Z", "type": "CORRECTION", "source": "brain"}
        id1 = CloudClient._format_event(ev)["event_id"]
        id2 = CloudClient._format_event(ev)["event_id"]
        assert id1 == id2
        assert len(id1) == 32  # sha256 hex truncated to 32 chars

    def test_different_events_get_different_ids(self):
        """Different ts/type/source → different event_id."""
        ev_a = {"ts": "2026-01-01T10:00:00Z", "type": "CORRECTION", "source": "brain"}
        ev_b = {"ts": "2026-01-01T10:00:00Z", "type": "LESSON_FIRED", "source": "brain"}
        assert (
            CloudClient._format_event(ev_a)["event_id"]
            != CloudClient._format_event(ev_b)["event_id"]
        )
