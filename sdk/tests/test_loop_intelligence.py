"""Tests for loop_intelligence.py — Activity tracking + pattern aggregation."""

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from gradata.enhancements.loop_intelligence import (
    aggregate_by_key,
    confidence_label,
    detect_manual,
    get_activity_stats,
    log_activity,
    log_outcome,
    log_prep,
    query_tagged_interactions,
    register_activity_types,
    register_outcomes,
    register_prep_types,
    update_markdown_table,
    update_patterns_file,
)


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary SQLite database."""
    return tmp_path / "test.db"


@pytest.fixture
def db_with_events(tmp_path):
    """Create a database with events table and DELTA_TAG events."""
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("""
        CREATE TABLE events (
            id INTEGER PRIMARY KEY,
            type TEXT,
            source TEXT,
            data_json TEXT,
            tags_json TEXT,
            session INTEGER
        )
    """)
    events = [
        ("DELTA_TAG", "test", json.dumps({"prospect": "Alice", "angle": "pain-point", "outcome": "reply"}),
         json.dumps(["prospect:Alice", "angle:pain-point"]), 1),
        ("DELTA_TAG", "test", json.dumps({"prospect": "Bob", "angle": "pain-point", "outcome": "no_reply"}),
         json.dumps(["prospect:Bob", "angle:pain-point"]), 1),
        ("DELTA_TAG", "test", json.dumps({"prospect": "Carol", "angle": "social-proof", "outcome": "meeting-booked"}),
         json.dumps(["prospect:Carol", "angle:social-proof"]), 2),
        ("DELTA_TAG", "test", json.dumps({"prospect": "Dave", "tone": "casual", "outcome": "reply", "source": "instantly"}),
         json.dumps(["tone:casual"]), 2),
    ]
    conn.executemany(
        "INSERT INTO events (type, source, data_json, tags_json, session) VALUES (?, ?, ?, ?, ?)",
        events,
    )
    conn.commit()
    conn.close()
    return db


# ─── Confidence Labels ───────────────────────────────────────────

class TestConfidenceLabel:
    def test_insufficient(self):
        assert confidence_label(0) == "[INSUFFICIENT]"
        assert confidence_label(2) == "[INSUFFICIENT]"

    def test_hypothesis(self):
        assert confidence_label(3) == "[HYPOTHESIS]"
        assert confidence_label(9) == "[HYPOTHESIS]"

    def test_emerging(self):
        assert confidence_label(10) == "[EMERGING]"
        assert confidence_label(24) == "[EMERGING]"

    def test_proven(self):
        assert confidence_label(25) == "[PROVEN]"

    def test_high_confidence(self):
        assert confidence_label(50) == "[HIGH CONFIDENCE]"

    def test_definitive(self):
        assert confidence_label(100) == "[DEFINITIVE]"


# ─── Activity Tracker ────────────────────────────────────────────

class TestLogActivity:
    def test_basic_log(self, tmp_db):
        result = log_activity(tmp_db, "email_sent", prospect="Alice", company="Acme",
                              detail="Follow-up", emit_event=False)
        assert result["id"] == 1
        assert "email_sent" in result["logged"]
        assert "Alice" in result["logged"]

    def test_roundtrip(self, tmp_db):
        log_activity(tmp_db, "email_sent", prospect="Alice", emit_event=False)
        log_activity(tmp_db, "call", prospect="Bob", emit_event=False)

        conn = sqlite3.connect(str(tmp_db))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM activity_log ORDER BY id").fetchall()
        conn.close()

        assert len(rows) == 2
        assert rows[0]["prospect"] == "Alice"
        assert rows[1]["type"] == "call"

    def test_custom_date(self, tmp_db):
        result = log_activity(tmp_db, "meeting", date="2026-01-15", emit_event=False)
        conn = sqlite3.connect(str(tmp_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT date FROM activity_log WHERE id = ?", (result["id"],)).fetchone()
        conn.close()
        assert row["date"] == "2026-01-15"


class TestLogPrep:
    def test_basic_prep(self, tmp_db):
        result = log_prep(tmp_db, "Alice", "cheat_sheet", prep_level=3)
        assert result["id"] == 1
        assert "cheat_sheet" in result["logged"]

    def test_stores_prep_level(self, tmp_db):
        log_prep(tmp_db, "Bob", "research", prep_level=2)
        conn = sqlite3.connect(str(tmp_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT prep_level FROM prep_outcomes WHERE id = 1").fetchone()
        conn.close()
        assert row["prep_level"] == 2


class TestLogOutcome:
    def test_links_to_existing_prep(self, tmp_db):
        log_prep(tmp_db, "Alice", "email_draft")
        result = log_outcome(tmp_db, "Alice", "email_draft", "reply", days=3)
        assert result["linked_to_prep"] is True

    def test_creates_standalone_if_no_prep(self, tmp_db):
        result = log_outcome(tmp_db, "Unknown", "research", "no_reply")
        assert result["linked_to_prep"] is False

    def test_calculates_days(self, tmp_db):
        log_prep(tmp_db, "Bob", "cheat_sheet", date="2026-03-01")
        result = log_outcome(tmp_db, "Bob", "cheat_sheet", "meeting_booked", date="2026-03-05")
        assert result["linked_to_prep"] is True

        conn = sqlite3.connect(str(tmp_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT days_to_outcome FROM prep_outcomes WHERE id = 1").fetchone()
        conn.close()
        assert row["days_to_outcome"] == 4


class TestDetectManual:
    def test_no_manual_when_all_logged(self, tmp_db):
        log_activity(tmp_db, "email_sent", emit_event=False)
        log_activity(tmp_db, "email_sent", emit_event=False)
        result = detect_manual(tmp_db, gmail_sent=2)
        assert result["manual_detected"] == 0

    def test_detects_gap(self, tmp_db):
        log_activity(tmp_db, "email_sent", emit_event=False)
        result = detect_manual(tmp_db, gmail_sent=3)
        assert result["manual_emails"] == 2
        assert result["manual_detected"] == 2


class TestGetActivityStats:
    def test_empty_db(self, tmp_db):
        stats = get_activity_stats(tmp_db, days=30)
        assert stats["total_activities"] == 0

    def test_counts(self, tmp_db):
        log_activity(tmp_db, "email_sent", source="claude_assisted", emit_event=False)
        log_activity(tmp_db, "call", source="manual", emit_event=False)
        log_prep(tmp_db, "Alice", "research")
        log_outcome(tmp_db, "Alice", "research", "reply")

        stats = get_activity_stats(tmp_db)
        assert stats["total_activities"] == 2
        assert stats["by_source"]["claude_assisted"] == 1
        assert stats["by_source"]["manual"] == 1
        assert stats["total_outcomes_resolved"] == 1


# ─── Pattern Aggregator ─────────────────────────────────────────

class TestQueryTaggedInteractions:
    def test_basic_query(self, db_with_events):
        interactions = query_tagged_interactions(db_with_events)
        # Should exclude the "instantly" source event
        assert len(interactions) == 3

    def test_session_filter(self, db_with_events):
        interactions = query_tagged_interactions(db_with_events, session=1)
        assert len(interactions) == 2

    def test_excludes_instantly(self, db_with_events):
        interactions = query_tagged_interactions(db_with_events)
        sources = [i.get("prospect") for i in interactions]
        assert "Dave" not in sources


class TestAggregateByKey:
    def test_aggregate_angle(self, db_with_events):
        interactions = query_tagged_interactions(db_with_events)
        by_angle = aggregate_by_key(interactions, "angle")
        assert "pain-point" in by_angle
        assert by_angle["pain-point"]["sent"] == 2
        assert by_angle["pain-point"]["replies"] == 1
        assert by_angle["pain-point"]["rate"] == 50.0

    def test_aggregate_empty(self):
        result = aggregate_by_key([], "angle")
        assert result == {}

    def test_confidence_in_result(self, db_with_events):
        interactions = query_tagged_interactions(db_with_events)
        by_angle = aggregate_by_key(interactions, "angle")
        assert by_angle["pain-point"]["confidence"] == "[INSUFFICIENT]"


class TestUpdateMarkdownTable:
    def test_updates_existing_row(self):
        md = """## Reply Rates by Angle
| Angle | Sent | Replies | Rate | Confidence |
|-------|------|---------|------|------------|
| pain-point | 5 | 1 | 20.0% | [HYPOTHESIS] |
"""
        new_data = {"pain-point": {"sent": 10, "replies": 3, "rate": 30.0, "confidence": "[EMERGING]"}}
        result = update_markdown_table(md, "Reply Rates by Angle", new_data)
        assert "10" in result
        assert "30.0%" in result

    def test_adds_new_row(self):
        md = """## Reply Rates by Angle
| Angle | Sent | Replies | Rate | Confidence |
|-------|------|---------|------|------------|
| pain-point | 5 | 1 | 20.0% | [HYPOTHESIS] |
"""
        new_data = {"social-proof": {"sent": 8, "replies": 4, "rate": 50.0, "confidence": "[HYPOTHESIS]"}}
        result = update_markdown_table(md, "Reply Rates by Angle", new_data)
        assert "Social Proof" in result
        assert "50.0%" in result

    def test_no_change_on_empty_data(self):
        md = "## Reply Rates by Angle\n| Angle | Sent |\n"
        result = update_markdown_table(md, "Reply Rates by Angle", {})
        assert result == md


class TestUpdatePatternsFile:
    def test_no_data(self, db_with_events, tmp_path):
        pf = tmp_path / "PATTERNS.md"
        pf.write_text("## Reply Rates by Angle\n| Angle | Sent | Replies | Rate | Confidence |\n|---|---|---|---|---|\n")
        # Use session 999 which has no data
        result = update_patterns_file(db_with_events, pf, session=999)
        assert result["status"] == "no_data"

    def test_file_not_found(self, db_with_events, tmp_path):
        result = update_patterns_file(db_with_events, tmp_path / "missing.md")
        assert "error" in result


# ─── Registry ────────────────────────────────────────────────────

class TestRegistries:
    def test_register_activity_types(self):
        register_activity_types("webinar", "podcast")
        from gradata.enhancements.loop_intelligence import _ACTIVITY_TYPES
        assert "webinar" in _ACTIVITY_TYPES
        assert "podcast" in _ACTIVITY_TYPES

    def test_register_prep_types(self):
        register_prep_types("presentation", "proposal")
        from gradata.enhancements.loop_intelligence import _PREP_TYPES
        assert "presentation" in _PREP_TYPES

    def test_register_positive_outcomes(self):
        register_outcomes("referral", positive=True)
        from gradata.enhancements.loop_intelligence import _POSITIVE_OUTCOMES
        assert "referral" in _POSITIVE_OUTCOMES
