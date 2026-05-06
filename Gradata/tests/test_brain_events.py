"""
Tests for BrainEventsMixin — brain.emit(), brain.query_events(), and
the underlying _events module (emit, query, dual-write behaviour).

Uses isolated brain instances (fresh temp dirs) and a BrainContext
pointing at an in-memory / temp SQLite for every test.

Run: cd sdk && python -m pytest tests/test_brain_events.py -v
"""

from __future__ import annotations

import sqlite3
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# 1. BrainEventsMixin — brain.emit()
# ---------------------------------------------------------------------------


class TestBrainEmit:
    """brain.emit() writes structured events and returns the enriched dict."""

    def test_returns_dict_with_required_keys(self, fresh_brain):
        event = fresh_brain.emit("TEST_EVENT", "pytest")
        for key in ("ts", "type", "source", "session", "data", "tags"):
            assert key in event, f"Missing key: {key}"

    def test_event_type_preserved(self, fresh_brain):
        event = fresh_brain.emit("MY_TYPE", "pytest")
        assert event["type"] == "MY_TYPE"

    def test_source_preserved(self, fresh_brain):
        event = fresh_brain.emit("X", "my.source")
        assert event["source"] == "my.source"

    def test_data_payload_stored(self, fresh_brain):
        event = fresh_brain.emit("X", "s", data={"foo": "bar", "n": 42})
        assert event["data"]["foo"] == "bar"
        assert event["data"]["n"] == 42

    def test_tags_stored(self, fresh_brain):
        event = fresh_brain.emit("X", "s", tags=["tag:a", "tag:b"])
        assert "tag:a" in event["tags"]
        assert "tag:b" in event["tags"]

    def test_explicit_session_stored(self, fresh_brain):
        event = fresh_brain.emit("X", "s", session=99)
        assert event["session"] == 99

    def test_emit_uses_active_session_when_none_passed(self, fresh_brain):
        fresh_brain.emit("SESSION_START", "pytest", {"session": 7}, session=7)
        event = fresh_brain.correct("draft text", "final text")
        assert event["session"] == 7

    def test_empty_data_defaults_to_empty_dict(self, fresh_brain):
        event = fresh_brain.emit("X", "s")
        assert isinstance(event["data"], dict)

    def test_empty_tags_defaults_to_list(self, fresh_brain):
        event = fresh_brain.emit("X", "s")
        assert isinstance(event["tags"], list)

    def test_persisted_metadata_included(self, fresh_brain):
        event = fresh_brain.emit("X", "s")
        assert "_persisted" in event
        assert "jsonl" in event["_persisted"]
        assert "sqlite" in event["_persisted"]

    def test_jsonl_file_written(self, fresh_brain):
        fresh_brain.emit("JSONL_CHECK", "pytest", data={"probe": True})
        jsonl = fresh_brain.ctx.events_jsonl
        assert jsonl.exists()
        lines = jsonl.read_text(encoding="utf-8").strip().splitlines()
        assert any("JSONL_CHECK" in line for line in lines)

    def test_sqlite_row_written(self, fresh_brain):
        fresh_brain.emit("SQLITE_CHECK", "pytest", data={"x": 1})
        db = fresh_brain.ctx.db_path
        with sqlite3.connect(str(db)) as conn:
            rows = conn.execute("SELECT type FROM events WHERE type='SQLITE_CHECK'").fetchall()
        assert len(rows) >= 1

    def test_multiple_events_accumulate(self, fresh_brain):
        for i in range(5):
            fresh_brain.emit("BATCH", "pytest", data={"i": i})
        db = fresh_brain.ctx.db_path
        with sqlite3.connect(str(db)) as conn:
            count = conn.execute("SELECT COUNT(*) FROM events WHERE type='BATCH'").fetchone()[0]
        assert count == 5

    def test_unicode_data_round_trips(self, fresh_brain):
        payload = {"emoji": "hello world", "unicode": "naïve résumé über"}
        event = fresh_brain.emit("UNICODE", "pytest", data=payload)
        assert event["data"]["unicode"] == "naïve résumé über"

    def test_large_data_dict_does_not_raise(self, fresh_brain):
        big = {f"key_{i}": "x" * 100 for i in range(100)}
        event = fresh_brain.emit("BIG", "pytest", data=big)
        assert event["type"] == "BIG"

    def test_none_data_handled_gracefully(self, fresh_brain):
        """Passing data=None should not raise; stored as empty dict."""
        event = fresh_brain.emit("X", "s", data=None)
        assert isinstance(event["data"], dict)

    def test_none_tags_handled_gracefully(self, fresh_brain):
        event = fresh_brain.emit("X", "s", tags=None)
        assert isinstance(event["tags"], list)


# ---------------------------------------------------------------------------
# 2. BrainEventsMixin — brain.query_events()
# ---------------------------------------------------------------------------


class TestBrainQueryEvents:
    """brain.query_events() retrieves events from the SQLite store."""

    def test_returns_list(self, fresh_brain):
        result = fresh_brain.query_events()
        assert isinstance(result, list)

    def test_returns_empty_for_empty_brain(self, fresh_brain):
        # No events emitted yet
        result = fresh_brain.query_events(event_type="NONEXISTENT_999")
        assert result == []

    def test_filter_by_event_type(self, brain_with_events):
        result = brain_with_events.query_events(event_type="CORRECTION")
        assert all(e["type"] == "CORRECTION" for e in result)

    def test_filter_by_session(self, fresh_brain):
        fresh_brain.emit("X", "s", session=7)
        fresh_brain.emit("X", "s", session=8)
        result = fresh_brain.query_events(session=7)
        assert all(e["session"] == 7 for e in result)

    def test_limit_respected(self, fresh_brain):
        for _ in range(10):
            fresh_brain.emit("LIM", "s")
        result = fresh_brain.query_events(event_type="LIM", limit=3)
        assert len(result) <= 3

    def test_returns_dicts_with_expected_fields(self, brain_with_events):
        results = brain_with_events.query_events(limit=1)
        if results:
            event = results[0]
            for field in ("id", "ts", "type", "source", "data", "tags"):
                assert field in event

    def test_last_n_sessions_returns_subset(self, fresh_brain):
        for s in range(1, 6):
            fresh_brain.emit("SESS", "s", session=s)
        result = fresh_brain.query_events(event_type="SESS", last_n_sessions=2)
        # Should only have sessions 4 and 5
        sessions = {e["session"] for e in result}
        assert sessions.issubset({4, 5})

    def test_no_filters_returns_all_up_to_limit(self, fresh_brain):
        for i in range(5):
            fresh_brain.emit(f"TYPE_{i}", "s")
        result = fresh_brain.query_events(limit=100)
        assert len(result) >= 5


# ---------------------------------------------------------------------------
# 3. _events module — emit() directly with BrainContext
# ---------------------------------------------------------------------------


class TestEventsModule:
    """Unit tests for gradata._events.emit() using BrainContext injection."""

    def test_emit_with_explicit_ctx(self, brain_dir):
        from gradata._events import emit
        from gradata._paths import BrainContext

        ctx = BrainContext.from_brain_dir(brain_dir)

        event = emit("DIRECT", "test", data={"val": 1}, ctx=ctx)
        assert event["type"] == "DIRECT"
        assert event["data"]["val"] == 1

    def test_emit_creates_jsonl_file(self, brain_dir):
        from gradata._events import emit
        from gradata._paths import BrainContext

        ctx = BrainContext.from_brain_dir(brain_dir)

        emit("FILE_TEST", "test", ctx=ctx)
        assert ctx.events_jsonl.exists()

    def test_emit_creates_sqlite_db(self, brain_dir):
        from gradata._events import emit
        from gradata._paths import BrainContext

        ctx = BrainContext.from_brain_dir(brain_dir)

        emit("DB_TEST", "test", ctx=ctx)
        assert ctx.db_path.exists()

    def test_emit_raises_when_both_backends_fail(self, brain_dir):
        """If both JSONL and SQLite fail, EventPersistenceError is raised."""
        from gradata._events import emit
        from gradata._paths import BrainContext
        from gradata.exceptions import EventPersistenceError

        ctx = BrainContext.from_brain_dir(brain_dir)

        # Patch both write paths to raise
        with patch("builtins.open", side_effect=PermissionError("no write")):
            with patch("sqlite3.connect", side_effect=sqlite3.OperationalError("no db")):
                with pytest.raises(EventPersistenceError):
                    emit("FAIL_BOTH", "test", ctx=ctx)

    def test_emit_succeeds_with_only_jsonl(self, brain_dir):
        """If SQLite fails but JSONL succeeds, no exception is raised."""
        from gradata._events import emit
        from gradata._paths import BrainContext

        ctx = BrainContext.from_brain_dir(brain_dir)

        with patch("sqlite3.connect", side_effect=sqlite3.OperationalError("db fail")):
            # Should NOT raise — JSONL alone is sufficient
            event = emit("JSONL_ONLY", "test", ctx=ctx)
        assert event["_persisted"]["jsonl"] is True
        assert event["_persisted"]["sqlite"] is False

    def test_emit_valid_from_defaults_to_timestamp(self, brain_dir):
        from gradata._events import emit
        from gradata._paths import BrainContext

        ctx = BrainContext.from_brain_dir(brain_dir)

        event = emit("VF_TEST", "test", ctx=ctx)
        assert event.get("valid_from") is not None

    def test_query_returns_emitted_event(self, brain_dir):
        from gradata._events import emit, query
        from gradata._paths import BrainContext

        ctx = BrainContext.from_brain_dir(brain_dir)

        emit("QUERY_TARGET", "test", data={"marker": "xyz"}, ctx=ctx)
        results = query(event_type="QUERY_TARGET", ctx=ctx)

        assert len(results) >= 1
        assert results[0]["data"]["marker"] == "xyz"

    def test_query_active_only_excludes_expired(self, brain_dir):
        from gradata._events import emit, query
        from gradata._paths import BrainContext

        ctx = BrainContext.from_brain_dir(brain_dir)

        # Emit an event with a past valid_until
        emit("ACTIVE_TEST", "test", valid_until="2000-01-01T00:00:00+00:00", ctx=ctx)
        emit("ACTIVE_TEST", "test", ctx=ctx)  # no expiry

        results = query(event_type="ACTIVE_TEST", active_only=True, ctx=ctx)
        # Only the non-expired event should appear
        assert all(r["valid_until"] is None for r in results)


# ---------------------------------------------------------------------------
# 4. BrainEventsMixin — brain.observe() (passive memory extraction)
# ---------------------------------------------------------------------------


class TestBrainObserve:
    """brain.observe() extracts facts from conversations or returns [] gracefully."""

    def test_returns_list_when_extractor_unavailable(self, fresh_brain):
        """If gradata_cloud and enhancements.memory_extraction are both absent,
        observe() must return an empty list without raising."""
        with patch.dict(
            "sys.modules",
            {
                "gradata_cloud": None,
                "gradata_cloud.scoring": None,
                "gradata_cloud.scoring.memory_extraction": None,
                "gradata.enhancements.memory_extraction": None,
            },
        ):
            result = fresh_brain.observe([{"role": "user", "content": "hello"}])
        assert isinstance(result, list)

    def test_empty_messages_returns_empty_list(self, fresh_brain):
        with patch.dict(
            "sys.modules",
            {
                "gradata_cloud": None,
                "gradata_cloud.scoring": None,
                "gradata_cloud.scoring.memory_extraction": None,
                "gradata.enhancements.memory_extraction": None,
            },
        ):
            result = fresh_brain.observe([])
        assert result == []

    def test_observe_returns_list_type(self, fresh_brain):
        # Even if memory extraction is available, must return list
        with patch.dict(
            "sys.modules",
            {
                "gradata_cloud": None,
                "gradata_cloud.scoring": None,
                "gradata_cloud.scoring.memory_extraction": None,
                "gradata.enhancements.memory_extraction": None,
            },
        ):
            result = fresh_brain.observe([{"role": "assistant", "content": "I can help."}])
        assert isinstance(result, list)
