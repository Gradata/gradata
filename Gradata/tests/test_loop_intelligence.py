"""Tests for scoring/loop_intelligence.py — all public functions + private helpers.
SQLite fixtures for DB-backed functions. 100% line coverage."""
import json
import sqlite3
import unittest.mock as mock
from pathlib import Path

import pytest

from gradata.enhancements.scoring.loop_intelligence import (
    _ACTIVITY_TYPES, _OUTCOMES, _POSITIVE_OUTCOMES, _PREP_TYPES,
    _get_db, _init_tables,
    aggregate_by_key, confidence_label, detect_manual, get_activity_stats,
    log_activity, log_outcome, log_prep,
    query_tagged_interactions, register_activity_types, register_outcomes,
    register_prep_types, update_markdown_table, update_patterns_file,
)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def make_activity_db(tmp_path: Path) -> Path:
    db = tmp_path / "system.db"
    conn = sqlite3.connect(str(db))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL,
            type TEXT NOT NULL, prospect TEXT, company TEXT, detail TEXT,
            source TEXT DEFAULT 'claude_assisted', prep_level INTEGER DEFAULT 0,
            session INTEGER, timestamp TEXT
        );
        CREATE TABLE IF NOT EXISTS prep_outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL,
            prospect TEXT NOT NULL, prep_type TEXT NOT NULL,
            prep_level INTEGER DEFAULT 0, outcome TEXT, days_to_outcome INTEGER,
            claude_assisted INTEGER DEFAULT 1, session INTEGER, timestamp TEXT
        );
    """)
    conn.commit(); conn.close()
    return db


def make_events_db(tmp_path: Path) -> Path:
    db = tmp_path / "events.db"
    conn = sqlite3.connect(str(db))
    conn.execute("""CREATE TABLE events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, session INTEGER,
        type TEXT, source TEXT, data_json TEXT, tags_json TEXT)""")
    conn.commit(); conn.close()
    return db


def insert_event(db: Path, session: int, data: dict, tags: list) -> None:
    conn = sqlite3.connect(str(db))
    conn.execute(
        "INSERT INTO events (session, type, data_json, tags_json) VALUES (?, 'DELTA_TAG', ?, ?)",
        (session, json.dumps(data), json.dumps(tags)),
    )
    conn.commit(); conn.close()


# ---------------------------------------------------------------------------
# Registries
# ---------------------------------------------------------------------------

class TestRegistries:
    def test_register_activity_types(self):
        register_activity_types("_test_act_x")
        assert "_test_act_x" in _ACTIVITY_TYPES
        _ACTIVITY_TYPES.discard("_test_act_x")

    def test_register_prep_types(self):
        register_prep_types("_test_prep_x")
        assert "_test_prep_x" in _PREP_TYPES
        _PREP_TYPES.discard("_test_prep_x")

    def test_register_outcomes_non_positive(self):
        register_outcomes("_test_out_x")
        assert "_test_out_x" in _OUTCOMES
        assert "_test_out_x" not in _POSITIVE_OUTCOMES
        _OUTCOMES.discard("_test_out_x")

    def test_register_outcomes_positive(self):
        register_outcomes("_test_out_pos", positive=True)
        assert "_test_out_pos" in _OUTCOMES and "_test_out_pos" in _POSITIVE_OUTCOMES
        _OUTCOMES.discard("_test_out_pos"); _POSITIVE_OUTCOMES.discard("_test_out_pos")


# ---------------------------------------------------------------------------
# confidence_label — all 6 bands + boundaries
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n,expected", [
    (0, "[INSUFFICIENT]"), (2, "[INSUFFICIENT]"),
    (3, "[HYPOTHESIS]"),   (9, "[HYPOTHESIS]"),
    (10, "[EMERGING]"),    (24, "[EMERGING]"),
    (25, "[PROVEN]"),      (49, "[PROVEN]"),
    (50, "[HIGH CONFIDENCE]"), (99, "[HIGH CONFIDENCE]"),
    (100, "[DEFINITIVE]"), (10000, "[DEFINITIVE]"),
])
def test_confidence_label(n, expected):
    assert confidence_label(n) == expected


# ---------------------------------------------------------------------------
# _get_db / _init_tables
# ---------------------------------------------------------------------------

class TestGetDbInitTables:
    def test_returns_connection_with_row_factory(self, tmp_path):
        conn = _get_db(tmp_path / "test.db")
        assert conn.row_factory == sqlite3.Row
        conn.close()

    def test_init_tables_creates_both_tables(self, tmp_path):
        conn = _get_db(tmp_path / "test.db")
        _init_tables(conn)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"activity_log", "prep_outcomes"}.issubset(tables)
        conn.close()

    def test_init_tables_idempotent(self, tmp_path):
        conn = _get_db(tmp_path / "test.db")
        _init_tables(conn); _init_tables(conn)  # must not raise
        conn.close()


# ---------------------------------------------------------------------------
# log_activity
# ---------------------------------------------------------------------------

class TestLogActivity:
    def test_returns_id_and_logged_string(self, tmp_path):
        db = make_activity_db(tmp_path)
        r = log_activity(db, "email_sent", prospect="Alice", emit_event=False)
        assert isinstance(r["id"], int) and "email_sent" in r["logged"]

    def test_source_and_date_persisted(self, tmp_path):
        db = make_activity_db(tmp_path)
        log_activity(db, "call", source="manual", date="2025-01-15", emit_event=False)
        conn = sqlite3.connect(str(db))
        row = conn.execute("SELECT source, date FROM activity_log").fetchone()
        conn.close()
        assert row[0] == "manual" and row[1] == "2025-01-15"

    def test_sequential_ids(self, tmp_path):
        db = make_activity_db(tmp_path)
        r1 = log_activity(db, "email_sent", emit_event=False)
        r2 = log_activity(db, "email_sent", emit_event=False)
        assert r2["id"] > r1["id"]

    def test_emit_exception_suppressed(self, tmp_path):
        db = make_activity_db(tmp_path)
        with mock.patch(
            "gradata.enhancements.scoring.loop_intelligence._emit_event_fn",
            side_effect=RuntimeError("broken"),
        ):
            result = log_activity(db, "email_sent", emit_event=True)
        assert result["id"] is not None


# ---------------------------------------------------------------------------
# log_prep
# ---------------------------------------------------------------------------

class TestLogPrep:
    def test_returns_id_and_logged_string(self, tmp_path):
        db = make_activity_db(tmp_path)
        r = log_prep(db, "Alice", "research")
        assert isinstance(r["id"], int) and "research" in r["logged"]

    def test_outcome_initially_null_and_date_persisted(self, tmp_path):
        db = make_activity_db(tmp_path)
        log_prep(db, "Dave", "personalization", date="2025-03-01")
        conn = sqlite3.connect(str(db))
        row = conn.execute("SELECT outcome, date FROM prep_outcomes").fetchone()
        conn.close()
        assert row[0] is None and row[1] == "2025-03-01"


# ---------------------------------------------------------------------------
# log_outcome
# ---------------------------------------------------------------------------

class TestLogOutcome:
    def test_links_to_existing_prep(self, tmp_path):
        db = make_activity_db(tmp_path)
        prep = log_prep(db, "Frank", "research")
        result = log_outcome(db, "Frank", "research", "reply")
        assert result["linked_to_prep"] is True and result["id"] == prep["id"]

    def test_creates_standalone_when_no_prep(self, tmp_path):
        db = make_activity_db(tmp_path)
        result = log_outcome(db, "Grace", "research", "reply")
        assert result["linked_to_prep"] is False and isinstance(result["id"], int)

    def test_auto_calculates_days_to_outcome(self, tmp_path):
        db = make_activity_db(tmp_path)
        log_prep(db, "Hank", "research", date="2025-01-01")
        log_outcome(db, "Hank", "research", "meeting_booked", days=0, date="2025-01-10")
        conn = sqlite3.connect(str(db))
        row = conn.execute("SELECT days_to_outcome FROM prep_outcomes WHERE prospect='Hank'").fetchone()
        conn.close()
        assert row[0] == 9

    def test_explicit_days_preserved_when_nonzero(self, tmp_path):
        db = make_activity_db(tmp_path)
        log_prep(db, "Irene", "research", date="2025-01-01")
        log_outcome(db, "Irene", "research", "reply", days=5, date="2025-01-15")
        conn = sqlite3.connect(str(db))
        row = conn.execute("SELECT days_to_outcome FROM prep_outcomes WHERE prospect='Irene'").fetchone()
        conn.close()
        assert row[0] == 5

    def test_links_most_recent_unresolved(self, tmp_path):
        db = make_activity_db(tmp_path)
        r1 = log_prep(db, "Jack", "research", date="2025-01-01")
        r2 = log_prep(db, "Jack", "research", date="2025-01-10")
        log_outcome(db, "Jack", "research", "reply")
        conn = sqlite3.connect(str(db))
        out1 = conn.execute("SELECT outcome FROM prep_outcomes WHERE id=?", (r1["id"],)).fetchone()[0]
        out2 = conn.execute("SELECT outcome FROM prep_outcomes WHERE id=?", (r2["id"],)).fetchone()[0]
        conn.close()
        assert out1 is None and out2 == "reply"

    def test_malformed_date_silenced(self, tmp_path):
        # ValueError from strptime is suppressed; row still updated
        db = make_activity_db(tmp_path)
        conn = sqlite3.connect(str(db))
        conn.execute("INSERT INTO prep_outcomes (date, prospect, prep_type) VALUES (?, ?, ?)",
                     ("not-a-date", "Zara", "research"))
        conn.commit(); conn.close()
        assert log_outcome(db, "Zara", "research", "reply", days=0, date="2025-01-10")["linked_to_prep"] is True


# ---------------------------------------------------------------------------
# detect_manual
# ---------------------------------------------------------------------------

class TestDetectManual:
    def test_zero_diff_returns_nothing_detected(self, tmp_path):
        db = make_activity_db(tmp_path)
        r = detect_manual(db, gmail_sent=0, crm_updates=0)
        assert r["manual_detected"] == 0 and r["logged"] == []

    def test_gmail_exceeds_ai_creates_manual_emails(self, tmp_path):
        db = make_activity_db(tmp_path)
        log_activity(db, "email_sent", source="claude_assisted", date="2025-06-01", emit_event=False)
        r = detect_manual(db, gmail_sent=3, crm_updates=0, date="2025-06-01")
        assert r["manual_emails"] == 2 and r["manual_detected"] == 2

    def test_crm_diff_creates_manual_crm_rows(self, tmp_path):
        db = make_activity_db(tmp_path)
        r = detect_manual(db, gmail_sent=0, crm_updates=3, session_logged=1)
        assert r["manual_crm"] == 2

    def test_ai_count_in_result(self, tmp_path):
        db = make_activity_db(tmp_path)
        log_activity(db, "email_sent", source="claude_assisted", date="2025-06-01", emit_event=False)
        r = detect_manual(db, gmail_sent=1, crm_updates=0, date="2025-06-01")
        assert r["ai_logged_today"] == 1 and r["manual_emails"] == 0


# ---------------------------------------------------------------------------
# get_activity_stats
# ---------------------------------------------------------------------------

class TestGetActivityStats:
    def test_empty_db_returns_zeros(self, tmp_path):
        db = make_activity_db(tmp_path)
        s = get_activity_stats(db, days=30)
        assert s["total_activities"] == 0 and s["by_source"] == {} and s["period_days"] == 30

    def test_by_source_and_by_type(self, tmp_path):
        db = make_activity_db(tmp_path)
        log_activity(db, "email_sent", source="claude_assisted", emit_event=False)
        log_activity(db, "email_sent", source="claude_assisted", emit_event=False)
        log_activity(db, "call", source="manual", emit_event=False)
        s = get_activity_stats(db, days=30)
        assert s["by_source"]["claude_assisted"] == 2 and s["by_type"]["call"] == 1

    def test_prep_effectiveness_rate(self, tmp_path):
        db = make_activity_db(tmp_path)
        log_prep(db, "Alice", "research", prep_level=1)
        log_prep(db, "Bob", "research", prep_level=1)
        log_outcome(db, "Alice", "research", "reply")
        log_outcome(db, "Bob", "research", "no_reply")
        s = get_activity_stats(db, days=30)
        lvl1 = next(x for x in s["prep_effectiveness"] if x["level"] == 1)
        assert lvl1["rate"] == pytest.approx(50.0) and lvl1["total"] == 2

    def test_pending_outcomes_counted(self, tmp_path):
        db = make_activity_db(tmp_path)
        log_prep(db, "Carol", "research")
        s = get_activity_stats(db, days=30)
        assert s["pending_outcomes"] == 1 and s["total_outcomes_resolved"] == 0


# ---------------------------------------------------------------------------
# query_tagged_interactions
# ---------------------------------------------------------------------------

class TestQueryTaggedInteractions:
    def test_empty_db_returns_empty(self, tmp_path):
        assert query_tagged_interactions(make_events_db(tmp_path)) == []

    def test_tags_parsed_into_fields(self, tmp_path):
        db = make_events_db(tmp_path)
        insert_event(db, 1, {"source": "claude_assisted"},
                     ["prospect:Alice", "angle:roi", "tone:confident",
                      "persona:ceo", "outcome:reply", "framework:spin"])
        r = query_tagged_interactions(db)[0]
        assert r["prospect"] == "Alice" and r["angle"] == "roi" and r["outcome"] == "reply"

    def test_excludes_instantly_by_default(self, tmp_path):
        db = make_events_db(tmp_path)
        insert_event(db, 1, {"source": "instantly"}, [])
        insert_event(db, 2, {"source": "claude_assisted"}, [])
        assert len(query_tagged_interactions(db)) == 1

    def test_session_filter(self, tmp_path):
        db = make_events_db(tmp_path)
        insert_event(db, 1, {"source": "claude_assisted"}, [])
        insert_event(db, 2, {"source": "claude_assisted"}, [])
        assert len(query_tagged_interactions(db, session=1)) == 1

    def test_null_json_handled_gracefully(self, tmp_path):
        db = make_events_db(tmp_path)
        conn = sqlite3.connect(str(db))
        conn.execute("INSERT INTO events (session, type, data_json, tags_json) VALUES (1,'DELTA_TAG',NULL,NULL)")
        conn.commit(); conn.close()
        result = query_tagged_interactions(db)
        assert isinstance(result, list)

    def test_missing_table_returns_empty(self, tmp_path):
        assert query_tagged_interactions(tmp_path / "empty.db") == []

    def test_outcome_defaults_to_pending(self, tmp_path):
        db = make_events_db(tmp_path)
        insert_event(db, 1, {"source": "claude_assisted"}, [])
        assert query_tagged_interactions(db)[0]["outcome"] == "pending"


# ---------------------------------------------------------------------------
# aggregate_by_key
# ---------------------------------------------------------------------------

def _ints(rows):
    return [{"angle": a, "outcome": o, "tone": "", "persona": "",
             "channel": "", "prospect": "", "framework": ""} for a, o in rows]


class TestAggregateByKey:
    def test_empty_returns_empty(self):
        assert aggregate_by_key([], "angle") == {}

    def test_blank_key_skipped(self):
        assert aggregate_by_key([{"angle": "", "outcome": "reply", "tone": "", "persona": "",
                                   "channel": "", "prospect": "", "framework": ""}], "angle") == {}

    def test_sent_replies_rate(self):
        r = aggregate_by_key(_ints([("roi", "reply"), ("roi", "reply"), ("roi", "no_reply"), ("roi", "no_reply")]), "angle")
        assert r["roi"]["sent"] == 4 and r["roi"]["replies"] == 2 and r["roi"]["rate"] == pytest.approx(50.0)

    def test_confidence_label_applied(self):
        r = aggregate_by_key(_ints([("roi", "pending")]), "angle")
        assert r["roi"]["confidence"] == "[INSUFFICIENT]"

    def test_custom_positive_outcomes(self):
        r = aggregate_by_key(_ints([("roi", "custom_win"), ("roi", "no_reply")]), "angle",
                             positive_outcomes={"custom_win"})
        assert r["roi"]["replies"] == 1

    def test_multiple_keys_independent(self):
        r = aggregate_by_key(_ints([("roi", "reply"), ("pain", "reply"), ("roi", "no_reply")]), "angle")
        assert r["roi"]["sent"] == 2 and r["pain"]["sent"] == 1


# ---------------------------------------------------------------------------
# update_markdown_table
# ---------------------------------------------------------------------------

SAMPLE_MD = (
    "# Playbook\n\n"
    "## Reply Rates by Angle\n\n"
    "| Angle | Sent | Replies | Rate | Confidence |\n"
    "|-------|------|---------|------|------------|\n"
    "| roi | 10 | 3 | 30.0% | [EMERGING] |\n"
    "| pain | 5 | 1 | 20.0% | [HYPOTHESIS] |\n\n"
    "## Other Section\nSome content.\n"
)

TIER_MD = (
    "## Reply Rates by Angle\n\n"
    "| Angle | Sent | Replies | Rate | Confidence | Tier | Notes |\n"
    "|-------|------|---------|------|------------|------|-------|\n"
    "| roi | 10 | 3 | 30.0% | [EMERGING] | Pipeline | manual |\n\n"
)


class TestUpdateMarkdownTable:
    def test_no_data_unchanged(self):
        assert update_markdown_table(SAMPLE_MD, "Reply Rates by Angle", {}) == SAMPLE_MD

    def test_updates_existing_row(self):
        r = update_markdown_table(SAMPLE_MD, "Reply Rates by Angle",
                                  {"roi": {"sent": 15, "replies": 5, "rate": 33.3, "confidence": "[EMERGING]"}})
        assert "15" in r and "33.3" in r

    def test_adds_new_row(self):
        r = update_markdown_table(SAMPLE_MD, "Reply Rates by Angle",
                                  {"urgency": {"sent": 3, "replies": 1, "rate": 33.3, "confidence": "[HYPOTHESIS]"}})
        assert "Urgency" in r

    def test_section_boundary_stops_update(self):
        r = update_markdown_table(SAMPLE_MD, "Reply Rates by Angle",
                                  {"roi": {"sent": 99, "replies": 0, "rate": 0.0, "confidence": "[HYPOTHESIS]"}})
        # roi in "Reply Rates by Angle" gets updated
        assert "99" in r

    def test_missing_section_unchanged(self):
        assert update_markdown_table(SAMPLE_MD, "Nonexistent", {"roi": {"sent": 99, "replies": 0, "rate": 0.0, "confidence": "[HYPOTHESIS]"}}) == SAMPLE_MD

    def test_dash_to_title(self):
        r = update_markdown_table(SAMPLE_MD, "Reply Rates by Angle",
                                  {"problem-agitate": {"sent": 2, "replies": 0, "rate": 0.0, "confidence": "[INSUFFICIENT]"}})
        assert "Problem Agitate" in r

    def test_tier_column_update_existing(self):
        r = update_markdown_table(TIER_MD, "Reply Rates by Angle",
                                  {"roi": {"sent": 20, "replies": 8, "rate": 40.0, "confidence": "[EMERGING]"}})
        assert "Auto-updated" in r and "20" in r

    def test_tier_column_add_new(self):
        r = update_markdown_table(TIER_MD, "Reply Rates by Angle",
                                  {"urgency": {"sent": 5, "replies": 2, "rate": 40.0, "confidence": "[HYPOTHESIS]"}})
        assert "Auto-added" in r and "Urgency" in r

    def test_empty_cells_row_skipped(self):
        md = ("## Reply Rates by Angle\n\n| Angle | Sent | Replies | Rate | Confidence |\n"
              "|---|---|---|---|---|\n| | | | | |\n| roi | 5 | 1 | 20.0% | [HYPOTHESIS] |\n\n")
        r = update_markdown_table(md, "Reply Rates by Angle",
                                  {"roi": {"sent": 9, "replies": 2, "rate": 22.2, "confidence": "[HYPOTHESIS]"}})
        assert "9" in r

    def test_non_pipe_line_ends_table_traversal(self):
        md = ("## Reply Rates by Angle\n\n| Angle | Sent | Replies | Rate | Confidence |\n"
              "|---|---|---|---|---|\n| roi | 5 | 1 | 20.0% | [HYPOTHESIS] |\nSome prose.\n\n")
        assert isinstance(update_markdown_table(md, "Reply Rates by Angle",
                                                {"roi": {"sent": 9, "replies": 2, "rate": 22.2, "confidence": "[HYPOTHESIS]"}}), str)


# ---------------------------------------------------------------------------
# update_patterns_file
# ---------------------------------------------------------------------------

class TestUpdatePatternsFile:
    def test_missing_file_returns_error(self, tmp_path):
        db = make_events_db(tmp_path)
        r = update_patterns_file(db, tmp_path / "nonexistent.md")
        assert "error" in r

    def test_no_interactions_returns_no_data(self, tmp_path):
        db = make_events_db(tmp_path)
        pf = tmp_path / "patterns.md"
        pf.write_text("# Patterns\n", encoding="utf-8")
        r = update_patterns_file(db, pf)
        assert r["status"] == "no_data" and r["interactions"] == 0

    def test_dry_run_does_not_write_file(self, tmp_path):
        db = make_events_db(tmp_path)
        pf = tmp_path / "patterns.md"
        pf.write_text(SAMPLE_MD, encoding="utf-8")
        insert_event(db, 1, {"source": "claude_assisted"}, ["angle:roi", "outcome:reply"])
        original = pf.read_text(encoding="utf-8")
        update_patterns_file(db, pf, dry_run=True)
        assert pf.read_text(encoding="utf-8") == original

    def test_result_contains_aggregation_keys_and_dry_run_flag(self, tmp_path):
        db = make_events_db(tmp_path)
        pf = tmp_path / "patterns.md"
        pf.write_text(SAMPLE_MD, encoding="utf-8")
        insert_event(db, 1, {"source": "claude_assisted"},
                     ["angle:roi", "tone:confident", "persona:ceo", "framework:spin", "outcome:reply"])
        r = update_patterns_file(db, pf, dry_run=True)
        for key in ("by_angle", "by_tone", "by_persona", "by_framework", "dry_run"):
            assert key in r
        assert r["dry_run"] is True

    def test_new_interaction_updates_file(self, tmp_path):
        db = make_events_db(tmp_path)
        pf = tmp_path / "patterns.md"
        pf.write_text(SAMPLE_MD, encoding="utf-8")
        insert_event(db, 1, {"source": "claude_assisted"}, ["angle:urgency", "outcome:reply"])
        r = update_patterns_file(db, pf)
        assert r["status"] in ("updated", "no_changes") and r["interactions"] == 1
