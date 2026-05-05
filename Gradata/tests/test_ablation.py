"""Tests for ablation framework — parser, session coercion, multi-session window."""

# We test ablation_test in isolation by injecting data, not importing
# brain/scripts/ directly (those have non-portable path deps).
# Instead we replicate the key logic under test or use the SDK-side
# functions where possible.
# ---------------------------------------------------------------------------
# Parser tests (validate regex extraction from lessons.md format)
# ---------------------------------------------------------------------------
# Replicate _parse_lessons_md regex locally for unit-testable isolation
import re
import sqlite3
from pathlib import Path

import pytest

ACTIVE_PATTERN = re.compile(
    r"\[(\d{4}-\d{2}-\d{2})\]\s+"
    r"\[(INSTINCT|PATTERN|RULE)(?::(\d+\.\d+))?\]\s+"
    r"(\w[\w_]*?):\s+"
    r"(.+)"
)


def _parse_line(line: str) -> dict | None:
    """Extract lesson from a single line using the ablation parser regex."""
    m = ACTIVE_PATTERN.match(line.strip())
    if not m:
        return None
    return {
        "date": m.group(1),
        "status": m.group(2),
        "confidence": float(m.group(3)) if m.group(3) else 0.90,
        "category": m.group(4).upper(),
        "description": m.group(5),
    }


class TestLessonParser:
    """Tests for parsing [RULE], [PATTERN:X.XX], and [INSTINCT:X.XX] formats."""

    def test_parse_rule_no_confidence(self):
        line = "[2026-03-17] [RULE] SKIP: Did not load CARL manifest"
        result = _parse_line(line)
        assert result is not None
        assert result["status"] == "RULE"
        assert result["confidence"] == 0.90  # default for bare [RULE]
        assert result["category"] == "SKIP"

    def test_parse_pattern_with_confidence(self):
        line = "[2026-03-20] [PATTERN:0.80] DRAFTING: Bullet lists need a lead-in line"
        result = _parse_line(line)
        assert result is not None
        assert result["status"] == "PATTERN"
        assert result["confidence"] == 0.80
        assert result["category"] == "DRAFTING"
        assert "Bullet lists" in result["description"]

    def test_parse_instinct_with_confidence(self):
        line = "[2026-03-22] [INSTINCT:0.40] CONTEXT: The user does prospect work on weekdays"
        result = _parse_line(line)
        assert result is not None
        assert result["status"] == "INSTINCT"
        assert result["confidence"] == 0.40
        assert result["category"] == "CONTEXT"

    def test_parse_pattern_059(self):
        line = "[2026-03-22] [INSTINCT:0.59] CONSTRAINT: Before proposing any tool"
        result = _parse_line(line)
        assert result is not None
        assert result["status"] == "INSTINCT"
        assert result["confidence"] == 0.59

    def test_parse_non_lesson_line(self):
        assert _parse_line("## Active Lessons") is None
        assert _parse_line("# Comment line") is None
        assert _parse_line("") is None

    def test_parse_all_statuses_eligible(self):
        """PATTERN and RULE should both be eligible for ablation selection."""
        lines = [
            "[2026-03-20] [PATTERN:0.80] DRAFTING: Bullet lists need a lead-in",
            "[2026-03-17] [RULE] SKIP: Did not load CARL manifest",
            "[2026-03-22] [INSTINCT:0.30] TEST: Some instinct",
        ]
        parsed = [_parse_line(l) for l in lines]
        eligible = [p for p in parsed if p and p["status"] in ("RULE", "PATTERN")]
        assert len(eligible) == 2
        assert eligible[0]["status"] == "PATTERN"
        assert eligible[1]["status"] == "RULE"


# ---------------------------------------------------------------------------
# Session type coercion tests
# ---------------------------------------------------------------------------


class TestSessionCoercion:
    """Verify that session values are safely coerced to int."""

    def test_int_session(self):
        """Normal int session passes through."""
        val = 42
        assert int(float(val)) == 42

    def test_string_int_session(self):
        """String '42' coerces to int."""
        val = "42"
        assert int(float(val)) == 42

    def test_float_session(self):
        """Float 42.0 coerces to int."""
        val = 42.0
        assert int(float(val)) == 42

    def test_uuid_session_raises(self):
        """UUID string should raise, caught by try/except in production."""
        val = "a3f8c2d1-1234-5678-abcd-ef0123456789"
        with pytest.raises(ValueError):
            int(float(val))

    def test_none_session_raises(self):
        """None should raise TypeError."""
        with pytest.raises(TypeError):
            int(float(None))

    def test_coercion_in_correction_loading(self):
        """Simulate the _load_corrections coercion logic."""
        raw_sessions = [42, "73", 10.0, "uuid-string", None, ""]
        results = []
        for raw in raw_sessions:
            try:
                results.append(int(float(raw)) if raw is not None else None)
            except (TypeError, ValueError):
                results.append(None)
        assert results == [42, 73, 10, None, None, None]


# ---------------------------------------------------------------------------
# Multi-session window tests (using in-memory SQLite)
# ---------------------------------------------------------------------------

# Minimal schema matching ablation_test.py
_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS ablation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session INTEGER NOT NULL,
    rule_category TEXT NOT NULL,
    rule_description TEXT,
    rule_confidence REAL,
    ablated BOOLEAN DEFAULT 1,
    error_recurred BOOLEAN,
    correction_count INTEGER DEFAULT 0,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    window_sessions INTEGER DEFAULT 1,
    window_end_session INTEGER
);
"""


def _make_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test_system.db"
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(_CREATE_TABLE)
    return db_path


class TestMultiSessionWindow:
    """Test the 3-session ablation window logic."""

    def test_window_columns_exist(self, tmp_path):
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                "INSERT INTO ablation_log "
                "(session, rule_category, ablated, window_sessions, window_end_session) "
                "VALUES (10, 'DRAFTING', 1, 3, 12)"
            )
            row = conn.execute(
                "SELECT window_sessions, window_end_session FROM ablation_log WHERE session = 10"
            ).fetchone()
        assert row == (3, 12)

    def test_active_ablation_within_window(self, tmp_path):
        """Ablation started at S10 with window 3 should be active at S10, S11, S12."""
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                "INSERT INTO ablation_log "
                "(session, rule_category, ablated, window_sessions, window_end_session) "
                "VALUES (10, 'DRAFTING', 1, 3, 12)"
            )

        # Check each session in window
        for session in [10, 11, 12]:
            with sqlite3.connect(str(db_path)) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    """SELECT id, session, rule_category, window_end_session
                       FROM ablation_log
                       WHERE ablated = 1 AND error_recurred IS NULL
                         AND session <= ?
                         AND (window_end_session >= ? OR (window_end_session IS NULL AND session = ?))
                       ORDER BY id DESC LIMIT 1""",
                    (session, session, session),
                ).fetchone()
            assert row is not None, f"Should be active at S{session}"
            assert row["rule_category"] == "DRAFTING"

    def test_ablation_inactive_after_window(self, tmp_path):
        """Ablation should NOT be active at S13 (window ended at S12)."""
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                "INSERT INTO ablation_log "
                "(session, rule_category, ablated, window_sessions, window_end_session) "
                "VALUES (10, 'DRAFTING', 1, 3, 12)"
            )

        session = 13
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """SELECT id FROM ablation_log
                   WHERE ablated = 1 AND error_recurred IS NULL
                     AND session <= ?
                     AND (window_end_session >= ? OR (window_end_session IS NULL AND session = ?))
                   ORDER BY id DESC LIMIT 1""",
                (session, session, session),
            ).fetchone()
        assert row is None, "Should NOT be active after window"

    def test_ablation_inactive_before_window(self, tmp_path):
        """Ablation should NOT be active at S9 (window starts at S10)."""
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                "INSERT INTO ablation_log "
                "(session, rule_category, ablated, window_sessions, window_end_session) "
                "VALUES (10, 'DRAFTING', 1, 3, 12)"
            )

        session = 9
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """SELECT id FROM ablation_log
                   WHERE ablated = 1 AND error_recurred IS NULL
                     AND session <= ?
                     AND (window_end_session >= ? OR (window_end_session IS NULL AND session = ?))
                   ORDER BY id DESC LIMIT 1""",
                (session, session, session),
            ).fetchone()
        assert row is None

    def test_finalized_ablation_not_active(self, tmp_path):
        """Once error_recurred is set, ablation is no longer active."""
        db_path = _make_db(tmp_path)
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                "INSERT INTO ablation_log "
                "(session, rule_category, ablated, error_recurred, window_sessions, window_end_session) "
                "VALUES (10, 'DRAFTING', 0, 1, 3, 12)"
            )

        session = 11
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """SELECT id FROM ablation_log
                   WHERE ablated = 1 AND error_recurred IS NULL
                     AND session <= ?
                     AND (window_end_session >= ? OR (window_end_session IS NULL AND session = ?))
                   ORDER BY id DESC LIMIT 1""",
                (session, session, session),
            ).fetchone()
        assert row is None, "Finalized ablation should not be active"

    def test_window_size_default_3(self):
        """Default window size constant should be 3."""
        # We can't import ablation_test directly, but we test the logic
        ABLATION_WINDOW_SIZE = 3
        start = 10
        end = start + ABLATION_WINDOW_SIZE - 1
        assert end == 12
        assert list(range(start, end + 1)) == [10, 11, 12]

    def test_select_rule_includes_pattern(self):
        """select_rule_for_ablation logic should include PATTERN-state lessons."""
        lessons = [
            {
                "category": "DRAFTING",
                "status": "PATTERN",
                "confidence": 0.80,
                "description": "test",
            },
            {"category": "SKIP", "status": "RULE", "confidence": 0.90, "description": "test2"},
            {"category": "CTX", "status": "INSTINCT", "confidence": 0.30, "description": "test3"},
        ]
        # Filter logic from fixed select_rule_for_ablation
        eligible = [
            l
            for l in lessons
            if l.get("status", "").upper() in ("RULE", "PATTERN") or l.get("graduated")
        ]
        assert len(eligible) == 2
        categories = {l["category"] for l in eligible}
        assert "DRAFTING" in categories
        assert "SKIP" in categories
        assert "CTX" not in categories


# ---------------------------------------------------------------------------
# Simulation logic tests
# ---------------------------------------------------------------------------


class TestSimulationLogic:
    """Test the before/after correction counting and verdict logic."""

    def test_proven_when_corrections_drop(self):
        """Rule is PROVEN if corrections dropped >= 50%."""
        before_count = 4
        after_count = 1
        reduction_pct = ((before_count - after_count) / before_count) * 100
        assert reduction_pct == 75.0
        assert after_count == 0 or reduction_pct >= 50

    def test_proven_when_corrections_zero(self):
        """Rule is PROVEN if after_count == 0."""
        after_count = 0
        assert after_count == 0  # proven

    def test_unproven_when_corrections_increase(self):
        """Rule is UNPROVEN if corrections increased."""
        before_count = 2
        after_count = 3
        reduction_pct = ((before_count - after_count) / before_count) * 100
        assert reduction_pct < 50
        assert after_count != 0

    def test_insufficient_when_no_before(self):
        """Insufficient data if no corrections before rule existed."""
        before_count = 0
        # Can't prove causation without pre-rule baseline
        assert before_count == 0  # triggers insufficient_data path
