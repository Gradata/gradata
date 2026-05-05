"""Tests for the Audit Trail + Provenance API (audit.py + Brain.trace wrapper)."""

from __future__ import annotations

import json
import sqlite3
import textwrap
from datetime import UTC, datetime
from pathlib import Path

import pytest

from gradata.audit import (
    _scan_events_for_ids,
    query_provenance,
    trace_rule,
    write_provenance,
)

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_LESSONS = textwrap.dedent("""\
    # Lessons

    [2026-01-15] [RULE:0.95] DRAFTING: Never use em dashes in email prose
      Root cause: User corrected em dashes 8 times across sessions
      Fire count: 12 | Sessions since fire: 1 | Misfires: 0
      Corrections: evt_abc123, evt_def456

    [2026-02-10] [PATTERN:0.72] ACCURACY: Always verify data before sending
      Root cause: Sent unverified stats in demo prep
      Fire count: 5 | Sessions since fire: 3 | Misfires: 1
      Corrections: evt_ghi789

    [2026-03-01] [INSTINCT:0.42] PROCESS: Check calendar before scheduling
      Root cause: Double-booked a meeting
      Fire count: 2 | Sessions since fire: 7 | Misfires: 0
""")


@pytest.fixture()
def brain_dir(tmp_path: Path) -> Path:
    """Create a minimal brain directory with lessons.md, system.db, and events.jsonl."""
    d = tmp_path / "test-brain"
    d.mkdir()

    # Write lessons.md
    (d / "lessons.md").write_text(SAMPLE_LESSONS, encoding="utf-8")

    # Create system.db with required tables
    db = d / "system.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        """CREATE TABLE IF NOT EXISTS lesson_transitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_desc TEXT NOT NULL,
            category TEXT NOT NULL,
            old_state TEXT NOT NULL,
            new_state TEXT NOT NULL,
            confidence REAL,
            fire_count INTEGER DEFAULT 0,
            session INTEGER,
            transitioned_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS rule_provenance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id TEXT NOT NULL,
            correction_event_id TEXT,
            session INTEGER,
            timestamp TEXT NOT NULL,
            user_context TEXT
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_provenance_rule_id ON rule_provenance(rule_id)")
    # Insert a transition for the RULE lesson
    conn.execute(
        "INSERT INTO lesson_transitions "
        "(lesson_desc, category, old_state, new_state, confidence, fire_count, session, transitioned_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "Never use em dashes in email prose",
            "DRAFTING",
            "PATTERN",
            "RULE",
            0.95,
            12,
            5,
            "2026-01-15T00:00:00",
        ),
    )
    conn.commit()
    conn.close()

    # Write events.jsonl with sample events
    events = [
        {
            "id": "evt_abc123",
            "type": "CORRECTION",
            "ts": "2026-01-10T10:00:00Z",
            "data": {"draft": "old text", "final": "new text"},
            "session": 3,
        },
        {
            "id": "evt_def456",
            "type": "CORRECTION",
            "ts": "2026-01-12T14:00:00Z",
            "data": {"draft": "another old", "final": "another new"},
            "session": 4,
        },
        {
            "id": "evt_other",
            "type": "SESSION_END",
            "ts": "2026-01-12T15:00:00Z",
            "data": {},
            "session": 4,
        },
    ]
    events_path = d / "events.jsonl"
    with events_path.open("w", encoding="utf-8") as f:
        for evt in events:
            f.write(json.dumps(evt) + "\n")

    return d


# ---------------------------------------------------------------------------
# Tests: rule_provenance table
# ---------------------------------------------------------------------------


class TestRuleProvenanceTable:
    """Test that rule_provenance table exists and has correct schema."""

    def test_table_exists_after_migration(self, brain_dir: Path) -> None:
        """rule_provenance table should exist after migrations run."""
        from gradata._migrations import run_migrations

        # Drop the table first so we verify migrations actually create it
        db_path = brain_dir / "system.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("DROP TABLE IF EXISTS rule_provenance")
        conn.commit()
        conn.close()

        run_migrations(db_path)

        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='rule_provenance'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_table_has_correct_columns(self, brain_dir: Path) -> None:
        """rule_provenance should have the expected columns."""
        conn = sqlite3.connect(str(brain_dir / "system.db"))
        cursor = conn.execute("PRAGMA table_info(rule_provenance)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()
        expected = {"id", "rule_id", "correction_event_id", "session", "timestamp", "user_context"}
        assert expected == columns


# ---------------------------------------------------------------------------
# Tests: write_provenance + query_provenance
# ---------------------------------------------------------------------------


class TestWriteAndQueryProvenance:
    """Test write_provenance inserts and query_provenance reads."""

    def test_write_and_query(self, brain_dir: Path) -> None:
        """Written provenance rows should be queryable."""
        db = brain_dir / "system.db"
        now = datetime.now(UTC).isoformat()
        write_provenance(
            db,
            rule_id="abc123",
            correction_event_id="evt_001",
            session=5,
            timestamp=now,
            user_context="test context",
        )
        rows = query_provenance(db, rule_id="abc123")
        assert len(rows) == 1
        assert rows[0]["rule_id"] == "abc123"
        assert rows[0]["correction_event_id"] == "evt_001"
        assert rows[0]["session"] == 5
        assert rows[0]["user_context"] == "test context"

    def test_query_empty_for_no_matches(self, brain_dir: Path) -> None:
        """query_provenance should return empty list for unknown rule_id."""
        db = brain_dir / "system.db"
        rows = query_provenance(db, rule_id="nonexistent_rule")
        assert rows == []

    def test_query_all_without_filter(self, brain_dir: Path) -> None:
        """query_provenance without rule_id returns all rows."""
        db = brain_dir / "system.db"
        now = datetime.now(UTC).isoformat()
        write_provenance(
            db, rule_id="r1", correction_event_id="e1", session=1, timestamp=now, user_context=None
        )
        write_provenance(
            db, rule_id="r2", correction_event_id="e2", session=2, timestamp=now, user_context=None
        )
        rows = query_provenance(db)
        assert len(rows) >= 2

    def test_query_limit(self, brain_dir: Path) -> None:
        """query_provenance respects limit parameter."""
        db = brain_dir / "system.db"
        now = datetime.now(UTC).isoformat()
        for i in range(10):
            write_provenance(
                db,
                rule_id="same",
                correction_event_id=f"e{i}",
                session=i,
                timestamp=now,
                user_context=None,
            )
        rows = query_provenance(db, rule_id="same", limit=3)
        assert len(rows) == 3


# ---------------------------------------------------------------------------
# Tests: _scan_events_for_ids
# ---------------------------------------------------------------------------


class TestScanEventsForIds:
    """Test events.jsonl scanning."""

    def test_finds_matching_events(self, brain_dir: Path) -> None:
        """Should find events by their IDs."""
        events_path = brain_dir / "events.jsonl"
        found = _scan_events_for_ids(events_path, ["evt_abc123", "evt_def456"])
        assert len(found) == 2
        ids = {e["id"] for e in found}
        assert "evt_abc123" in ids
        assert "evt_def456" in ids

    def test_ignores_non_matching_ids(self, brain_dir: Path) -> None:
        """Should not return events that don't match requested IDs."""
        events_path = brain_dir / "events.jsonl"
        found = _scan_events_for_ids(events_path, ["evt_abc123"])
        assert len(found) == 1
        assert found[0]["id"] == "evt_abc123"

    def test_returns_empty_for_missing_file(self, tmp_path: Path) -> None:
        """Should return empty list if events.jsonl doesn't exist."""
        found = _scan_events_for_ids(tmp_path / "missing.jsonl", ["evt_abc123"])
        assert found == []


# ---------------------------------------------------------------------------
# Tests: trace_rule
# ---------------------------------------------------------------------------


class TestTraceRule:
    """Test the full trace_rule function."""

    def test_trace_known_rule(self, brain_dir: Path) -> None:
        """trace_rule should return provenance for a known rule."""
        from gradata.inspection import _load_lessons_from_path, _make_rule_id

        lessons = _load_lessons_from_path(brain_dir / "lessons.md")
        rule_lesson = next(l for l in lessons if l.state.value == "RULE")
        rid = _make_rule_id(rule_lesson)

        # Write provenance for this rule
        db = brain_dir / "system.db"
        now = datetime.now(UTC).isoformat()
        write_provenance(
            db,
            rule_id=rid,
            correction_event_id="evt_abc123",
            session=3,
            timestamp=now,
            user_context="test",
        )

        result = trace_rule(db, brain_dir / "events.jsonl", brain_dir / "lessons.md", rid)

        assert result["rule_id"] == rid
        assert "provenance" in result
        assert len(result["provenance"]) >= 1
        assert "corrections" in result

    def test_trace_unknown_rule(self, brain_dir: Path) -> None:
        """trace_rule should return error for unknown rule_id."""
        db = brain_dir / "system.db"
        result = trace_rule(
            db, brain_dir / "events.jsonl", brain_dir / "lessons.md", "unknown_rule_id"
        )
        assert "error" in result

    def test_trace_includes_transitions(self, brain_dir: Path) -> None:
        """trace_rule should include lesson_transitions from SQLite."""
        from gradata.inspection import _load_lessons_from_path, _make_rule_id

        lessons = _load_lessons_from_path(brain_dir / "lessons.md")
        rule_lesson = next(l for l in lessons if l.state.value == "RULE")
        rid = _make_rule_id(rule_lesson)

        result = trace_rule(
            db_path=brain_dir / "system.db",
            events_path=brain_dir / "events.jsonl",
            lessons_path=brain_dir / "lessons.md",
            rule_id=rid,
        )

        assert "transitions" in result
        assert len(result["transitions"]) >= 1


# ---------------------------------------------------------------------------
# Tests: Brain.trace() wrapper
# ---------------------------------------------------------------------------


class TestBrainTrace:
    """Test the Brain.trace() thin wrapper."""

    def test_brain_trace_returns_provenance(self, brain_dir: Path) -> None:
        """brain.trace() should delegate to audit.trace_rule."""
        from gradata.brain import Brain
        from gradata.inspection import _load_lessons_from_path, _make_rule_id

        brain = Brain(brain_dir)
        lessons = _load_lessons_from_path(brain_dir / "lessons.md")
        rule_lesson = next(l for l in lessons if l.state.value == "RULE")
        rid = _make_rule_id(rule_lesson)

        result = brain.trace(rid)
        assert result["rule_id"] == rid
        assert "provenance" in result
        assert "corrections" in result

    def test_brain_trace_unknown_returns_error(self, brain_dir: Path) -> None:
        """brain.trace() should return error dict for unknown rule_id."""
        from gradata.brain import Brain

        brain = Brain(brain_dir)
        result = brain.trace("nonexistent_id")
        assert "error" in result
