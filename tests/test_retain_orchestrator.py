"""Tests for RetainOrchestrator — 3-phase event persistence.

Covers:
1. Queue + flush writes events to events.jsonl
2. Delta detection: already-persisted events are skipped
3. Crash recovery: cursor file tracks last committed key
4. Empty queue returns zero written
5. Phase 3 failure does NOT roll back Phase 2 data
6. Phase 2 failure prevents Phase 3 from running
7. pending_count tracks correctly
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from gradata._events import RetainOrchestrator


# ── helpers ──────────────────────────────────────────────────────────────────


def _make_event(event_type: str = "TEST", source: str = "test", ts: str = "2026-01-01T00:00:00+00:00") -> dict:
    return {
        "ts": ts,
        "session": 1,
        "type": event_type,
        "source": source,
        "data": {"x": 1},
        "tags": [],
        "valid_from": ts,
        "valid_until": None,
    }


def _read_jsonl(path: Path) -> list[dict]:
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events


# ── tests ─────────────────────────────────────────────────────────────────────


class TestQueueAndFlush:
    """Test 1: queue + flush writes to events.jsonl."""

    def test_single_event_written(self, tmp_path: Path) -> None:
        orch = RetainOrchestrator(tmp_path)
        evt = _make_event()
        orch.queue(evt)
        result = orch.flush()

        assert result["written"] == 1
        assert orch.events_path.is_file()
        written = _read_jsonl(orch.events_path)
        assert len(written) == 1
        assert written[0]["type"] == "TEST"

    def test_multiple_events_written(self, tmp_path: Path) -> None:
        orch = RetainOrchestrator(tmp_path)
        for i in range(5):
            orch.queue(_make_event(ts=f"2026-01-0{i + 1}T00:00:00+00:00"))
        result = orch.flush()

        assert result["written"] == 5
        assert len(_read_jsonl(orch.events_path)) == 5

    def test_pending_cleared_after_flush(self, tmp_path: Path) -> None:
        orch = RetainOrchestrator(tmp_path)
        orch.queue(_make_event())
        orch.flush()
        assert orch.pending_count == 0

    def test_phase_keys_present(self, tmp_path: Path) -> None:
        orch = RetainOrchestrator(tmp_path)
        orch.queue(_make_event())
        result = orch.flush()

        assert "read" in result["phases"]
        assert "write" in result["phases"]
        assert "post" in result["phases"]


class TestDeltaDetection:
    """Test 2: already-persisted events are skipped on re-flush."""

    def test_duplicate_event_not_written_twice(self, tmp_path: Path) -> None:
        evt = _make_event()

        orch1 = RetainOrchestrator(tmp_path)
        orch1.queue(evt)
        orch1.flush()

        # Second orchestrator instance, same brain_dir — simulates crash + restart
        orch2 = RetainOrchestrator(tmp_path)
        orch2.queue(evt)  # same event again
        result = orch2.flush()

        assert result["written"] == 0
        # File still has exactly one line
        assert len(_read_jsonl(orch2.events_path)) == 1

    def test_new_event_still_written_when_some_duplicates(self, tmp_path: Path) -> None:
        evt_a = _make_event(ts="2026-01-01T00:00:00+00:00")
        evt_b = _make_event(ts="2026-01-02T00:00:00+00:00")

        orch1 = RetainOrchestrator(tmp_path)
        orch1.queue(evt_a)
        orch1.flush()

        orch2 = RetainOrchestrator(tmp_path)
        orch2.queue(evt_a)  # already exists
        orch2.queue(evt_b)  # genuinely new
        result = orch2.flush()

        assert result["written"] == 1
        assert len(_read_jsonl(orch2.events_path)) == 2

    def test_phase_read_reports_correct_counts(self, tmp_path: Path) -> None:
        evt = _make_event()
        orch = RetainOrchestrator(tmp_path)
        orch.queue(evt)
        orch.flush()

        orch2 = RetainOrchestrator(tmp_path)
        orch2.queue(evt)
        orch2.queue(_make_event(ts="2026-06-01T00:00:00+00:00"))
        result = orch2.flush()

        assert result["phases"]["read"]["existing_keys"] == 1
        assert result["phases"]["read"]["new"] == 1


class TestCrashRecovery:
    """Test 3: cursor file persists last committed key."""

    def test_cursor_file_created_after_flush(self, tmp_path: Path) -> None:
        orch = RetainOrchestrator(tmp_path)
        orch.queue(_make_event())
        orch.flush()

        assert orch._cursor_path.is_file()
        data = json.loads(orch._cursor_path.read_text(encoding="utf-8"))
        assert "last_committed_key" in data
        assert data["last_committed_key"] != ""

    def test_cursor_key_matches_last_event(self, tmp_path: Path) -> None:
        evt_a = _make_event(ts="2026-01-01T00:00:00+00:00")
        evt_b = _make_event(ts="2026-01-02T00:00:00+00:00")
        orch = RetainOrchestrator(tmp_path)
        orch.queue(evt_a)
        orch.queue(evt_b)
        orch.flush()

        expected_key = RetainOrchestrator._event_key(evt_b)
        data = json.loads(orch._cursor_path.read_text(encoding="utf-8"))
        assert data["last_committed_key"] == expected_key

    def test_cursor_loaded_on_reinit(self, tmp_path: Path) -> None:
        evt = _make_event()
        orch1 = RetainOrchestrator(tmp_path)
        orch1.queue(evt)
        orch1.flush()

        orch2 = RetainOrchestrator(tmp_path)
        assert orch2._last_committed_key == RetainOrchestrator._event_key(evt)

    def test_corrupt_cursor_falls_back_gracefully(self, tmp_path: Path) -> None:
        cursor_path = tmp_path / ".event_cursor.json"
        cursor_path.write_text("NOT VALID JSON", encoding="utf-8")

        # Should not raise; cursor simply returns None
        orch = RetainOrchestrator(tmp_path)
        assert orch._last_committed_key is None

    def test_no_cursor_file_no_crash(self, tmp_path: Path) -> None:
        orch = RetainOrchestrator(tmp_path)
        assert orch._last_committed_key is None


class TestEmptyQueue:
    """Test 4: empty queue returns zero written."""

    def test_empty_flush_returns_zero(self, tmp_path: Path) -> None:
        orch = RetainOrchestrator(tmp_path)
        result = orch.flush()

        assert result["written"] == 0
        assert result["errors"] == []
        # No phases key at all (fast-path exit)
        assert result.get("phases", {}) == {}

    def test_no_file_created_on_empty_flush(self, tmp_path: Path) -> None:
        orch = RetainOrchestrator(tmp_path)
        orch.flush()
        assert not orch.events_path.is_file()


class TestPhase3DoesNotBlockPhase2:
    """Test 5: Phase 3 failure does NOT prevent Phase 2 data from being readable."""

    def test_phase3_error_does_not_erase_written_data(self, tmp_path: Path) -> None:
        orch = RetainOrchestrator(tmp_path)
        orch.queue(_make_event())

        # Patch update_manifest to raise inside Phase 3
        with patch(
            "gradata._events.RetainOrchestrator.flush",
            wraps=orch.flush,
        ):
            # We simulate Phase 3 failure by patching the import inside flush
            import unittest.mock as mock

            with mock.patch.dict("sys.modules", {"gradata._brain_manifest": None}):
                result = orch.flush()

        # Phase 2 still succeeded
        assert result["written"] == 1
        assert orch.events_path.is_file()
        assert len(_read_jsonl(orch.events_path)) == 1

    def test_phase3_failure_recorded_in_errors_or_phases(self, tmp_path: Path) -> None:
        """Phase 3 failure is either silently handled or appears in errors — never raises."""
        orch = RetainOrchestrator(tmp_path)
        orch.queue(_make_event())

        # Patch to make manifest update raise
        with patch(
            "gradata._brain_manifest.update_manifest",
            side_effect=RuntimeError("manifest boom"),
            create=True,
        ):
            result = orch.flush()

        # The important thing: no exception propagated, Phase 2 data is there
        assert result["written"] == 1
        assert orch.events_path.is_file()


class TestPhase2FailurePreventsPhase3:
    """Test 6: Phase 2 failure prevents Phase 3 from running."""

    def test_phase2_io_failure_no_phase3_in_phases(self, tmp_path: Path) -> None:
        orch = RetainOrchestrator(tmp_path)
        orch.queue(_make_event())

        # _locked_append uses the builtin open(); patch it in gradata._events
        import builtins
        original_open = builtins.open

        def _bad_open(path, *args, **kwargs):
            if str(path).endswith("events.jsonl"):
                raise OSError("disk full")
            return original_open(path, *args, **kwargs)

        with patch("gradata._events.open", _bad_open):
            result = orch.flush()

        assert result["written"] == 0
        assert any("Phase 2" in e for e in result["errors"])
        # Phase 3 key must not be present when Phase 2 aborted
        assert "post" not in result.get("phases", {})

    def test_phase2_failure_pending_still_cleared(self, tmp_path: Path) -> None:
        orch = RetainOrchestrator(tmp_path)
        orch.queue(_make_event())

        import builtins
        original_open = builtins.open

        def _bad_open(path, *args, **kwargs):
            if str(path).endswith("events.jsonl"):
                raise OSError("disk full")
            return original_open(path, *args, **kwargs)

        with patch("gradata._events.open", _bad_open):
            orch.flush()

        # Pending cleared regardless of failure
        assert orch.pending_count == 0


class TestPendingCount:
    """Test 7: pending_count tracks correctly."""

    def test_starts_at_zero(self, tmp_path: Path) -> None:
        orch = RetainOrchestrator(tmp_path)
        assert orch.pending_count == 0

    def test_increments_with_queue(self, tmp_path: Path) -> None:
        orch = RetainOrchestrator(tmp_path)
        for i in range(4):
            orch.queue(_make_event(ts=f"2026-01-0{i + 1}T00:00:00+00:00"))
        assert orch.pending_count == 4

    def test_resets_to_zero_after_flush(self, tmp_path: Path) -> None:
        orch = RetainOrchestrator(tmp_path)
        orch.queue(_make_event())
        orch.queue(_make_event(ts="2026-02-01T00:00:00+00:00"))
        orch.flush()
        assert orch.pending_count == 0

    def test_resets_after_empty_flush(self, tmp_path: Path) -> None:
        orch = RetainOrchestrator(tmp_path)
        orch.flush()
        assert orch.pending_count == 0


class TestSQLiteWrite:
    """Bonus: when system.db exists, events are also written to it."""

    def test_events_inserted_into_db(self, tmp_path: Path) -> None:
        db_path = tmp_path / "system.db"
        # Pre-create table via _ensure_table
        with contextlib.closing(sqlite3.connect(str(db_path))) as conn:
            from gradata._events import _ensure_table
            _ensure_table(conn)

        orch = RetainOrchestrator(tmp_path)
        orch.queue(_make_event())
        result = orch.flush()

        assert result["written"] == 1
        # Verify DB row
        with contextlib.closing(sqlite3.connect(str(db_path))) as conn:
            rows = conn.execute("SELECT type, source FROM events").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "TEST"
        assert rows[0][1] == "test"


import contextlib  # noqa: E402 — imported at end to keep test logic readable
