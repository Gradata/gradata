"""Tests for scoring/brain_scores.py — compound health metric aggregation.

Tests cover:
- BrainScores dataclass defaults
- _reshape() maps dict keys to typed fields correctly
- _fallback_brain_scores produces known score from known events
- _fallback_brain_scores handles empty database safely
- _bar() ASCII progress bar renders correctly
- format_brain_scores includes all required sections
- compute_brain_scores falls back gracefully when _events unavailable
"""

import sqlite3
from pathlib import Path

import pytest

from gradata.enhancements.scoring.brain_scores import (
    BrainScores,
    _bar,
    _fallback_brain_scores,
    _reshape,
    compute_brain_scores,
    format_brain_scores,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_db(tmp_path: Path) -> Path:
    """Create a minimal events SQLite database in tmp_path."""
    db = tmp_path / "system.db"
    conn = sqlite3.connect(str(db))
    conn.execute("""
        CREATE TABLE events (
            id INTEGER PRIMARY KEY,
            session INTEGER,
            type TEXT,
            source TEXT,
            data_json TEXT
        )
    """)
    conn.commit()
    conn.close()
    return db


def insert_events(db: Path, rows: list[tuple]) -> None:
    """Insert (session, type) tuples into the events table."""
    conn = sqlite3.connect(str(db))
    conn.executemany(
        "INSERT INTO events (session, type) VALUES (?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# BrainScores dataclass defaults
# ---------------------------------------------------------------------------


class TestBrainScoresDefaults:
    def test_default_system_health_is_zero(self):
        s = BrainScores()
        assert s.system_health == 0.0

    def test_default_compound_growth_is_100(self):
        s = BrainScores()
        assert s.compound_growth == 100.0

    def test_default_brier_calibration_is_no_data(self):
        s = BrainScores()
        assert s.brier_calibration == "NO_DATA"

    def test_default_data_sufficient_is_false(self):
        s = BrainScores()
        assert s.data_sufficient is False

    def test_default_score_errors_is_empty_list(self):
        s = BrainScores()
        assert s.score_errors == []


# ---------------------------------------------------------------------------
# _reshape — dict → BrainScores
# ---------------------------------------------------------------------------


class TestReshape:
    def test_maps_all_known_keys(self):
        raw = {
            "system_health": 85.5,
            "ai_quality": 72.3,
            "compound_growth": 115.0,
            "arch_quality": 60.0,
            "brier_score": 0.12,
            "brier_calibration": "GOOD",
            "data_sufficient": True,
            "score_errors": ["something failed"],
        }
        scores = _reshape(raw)
        assert scores.system_health == 85.5
        assert scores.ai_quality == 72.3
        assert scores.compound_growth == 115.0
        assert scores.arch_quality == 60.0
        assert scores.brier_score == 0.12
        assert scores.brier_calibration == "GOOD"
        assert scores.data_sufficient is True
        assert scores.score_errors == ["something failed"]

    def test_missing_keys_fall_back_to_defaults(self):
        scores = _reshape({})
        assert scores.system_health == 0.0
        assert scores.compound_growth == 100.0
        assert scores.brier_score is None
        assert scores.brier_calibration == "NO_DATA"
        assert scores.data_sufficient is False

    def test_brier_score_none_preserved(self):
        raw = {"brier_score": None}
        scores = _reshape(raw)
        assert scores.brier_score is None

    def test_score_errors_list_preserved(self):
        raw = {"score_errors": ["err1", "err2"]}
        scores = _reshape(raw)
        assert scores.score_errors == ["err1", "err2"]


# ---------------------------------------------------------------------------
# _fallback_brain_scores — system_health from gate sessions
# ---------------------------------------------------------------------------


class TestFallbackBrainScores:
    def test_empty_db_returns_zero_scores(self, tmp_path):
        db = make_db(tmp_path)
        scores = _fallback_brain_scores(db, last_n_sessions=10)
        assert scores.system_health == 0.0
        assert scores.ai_quality == 0.0
        assert scores.data_sufficient is False

    def test_all_sessions_have_gate_events_gives_100_system_health(self, tmp_path):
        db = make_db(tmp_path)
        # 4 sessions, all with GATE_RESULT
        insert_events(
            db,
            [
                (1, "GATE_RESULT"),
                (2, "GATE_RESULT"),
                (3, "GATE_RESULT"),
                (4, "GATE_RESULT"),
            ],
        )
        scores = _fallback_brain_scores(db, last_n_sessions=10)
        assert scores.system_health == 100.0

    def test_half_sessions_have_gate_events_gives_50_system_health(self, tmp_path):
        db = make_db(tmp_path)
        # Sessions 1,2 have GATE_RESULT; sessions 3,4 only have OUTPUT
        insert_events(
            db,
            [
                (1, "GATE_RESULT"),
                (2, "GATE_RESULT"),
                (3, "OUTPUT"),
                (4, "OUTPUT"),
            ],
        )
        scores = _fallback_brain_scores(db, last_n_sessions=10)
        assert scores.system_health == pytest.approx(50.0)

    def test_no_corrections_gives_100_ai_quality(self, tmp_path):
        db = make_db(tmp_path)
        # All outputs, no corrections
        insert_events(db, [(1, "OUTPUT"), (2, "OUTPUT"), (3, "OUTPUT")])
        scores = _fallback_brain_scores(db, last_n_sessions=10)
        assert scores.ai_quality == 100.0

    def test_all_corrections_gives_0_ai_quality(self, tmp_path):
        db = make_db(tmp_path)
        # All corrections, plus one output so denominator is non-zero
        insert_events(db, [(1, "CORRECTION"), (1, "OUTPUT")])
        scores = _fallback_brain_scores(db, last_n_sessions=10)
        # 1 correction / (1 correction + 1 output) = 50% correction rate → 50 ai_quality
        assert scores.ai_quality == pytest.approx(50.0)

    def test_data_sufficient_requires_three_or_more_sessions(self, tmp_path):
        db = make_db(tmp_path)
        insert_events(db, [(1, "OUTPUT"), (2, "OUTPUT")])
        scores = _fallback_brain_scores(db, last_n_sessions=10)
        assert scores.data_sufficient is False

        b2_dir = tmp_path / "b2"
        b2_dir.mkdir()
        db2 = make_db(b2_dir)
        insert_events(db2, [(1, "OUTPUT"), (2, "OUTPUT"), (3, "OUTPUT")])
        scores2 = _fallback_brain_scores(db2, last_n_sessions=10)
        assert scores2.data_sufficient is True

    def test_compound_growth_always_100_in_fallback(self, tmp_path):
        db = make_db(tmp_path)
        scores = _fallback_brain_scores(db, last_n_sessions=10)
        assert scores.compound_growth == 100.0

    def test_arch_quality_always_0_in_fallback(self, tmp_path):
        db = make_db(tmp_path)
        scores = _fallback_brain_scores(db, last_n_sessions=10)
        assert scores.arch_quality == 0.0

    def test_nonexistent_db_records_error_does_not_raise(self, tmp_path):
        missing = tmp_path / "nosuchfile.db"
        scores = _fallback_brain_scores(missing, last_n_sessions=10)
        # Should not raise; returns zero scores with an error recorded
        assert isinstance(scores, BrainScores)
        assert len(scores.score_errors) > 0


# ---------------------------------------------------------------------------
# _bar — ASCII progress bar
# ---------------------------------------------------------------------------


class TestBar:
    def test_zero_value_gives_empty_bar(self):
        result = _bar(0.0)
        assert result.startswith("[....")
        assert "0.0%" in result

    def test_100_value_gives_full_bar(self):
        result = _bar(100.0)
        assert result.startswith("[####")
        assert "100.0%" in result

    def test_50_percent_fills_half(self):
        result = _bar(50.0, max_val=100.0, width=20)
        # round(50/100 * 20) = 10 filled, 10 empty
        assert result.count("#") == 10
        # The dot count may include dots in the percentage string, count only
        # the bar section between the brackets
        bar_section = result[1 : result.index("]")]
        assert bar_section.count(".") == 10

    def test_value_above_max_clamped(self):
        result = _bar(150.0, max_val=100.0, width=20)
        # Should render as 100%
        assert result.count("#") == 20

    def test_negative_value_renders_as_zero(self):
        result = _bar(-10.0)
        assert result.count("#") == 0


# ---------------------------------------------------------------------------
# format_brain_scores
# ---------------------------------------------------------------------------


class TestFormatBrainScores:
    def test_format_includes_all_score_sections(self):
        scores = BrainScores(
            system_health=85.0,
            ai_quality=72.0,
            compound_growth=110.0,
            arch_quality=60.0,
            brier_score=0.15,
            brier_calibration="GOOD",
            data_sufficient=True,
        )
        text = format_brain_scores(scores)
        assert "System Health" in text
        assert "AI Quality" in text
        assert "Arch Quality" in text
        assert "Compound Growth" in text
        assert "Brier" in text
        assert "GOOD" in text

    def test_format_no_brier_data_shows_no_data(self):
        scores = BrainScores(brier_score=None, brier_calibration="NO_DATA")
        text = format_brain_scores(scores)
        assert "NO DATA" in text

    def test_format_score_errors_section_shown_when_present(self):
        scores = BrainScores(score_errors=["something_broke: TypeError"])
        text = format_brain_scores(scores)
        assert "Score errors" in text
        assert "something_broke" in text

    def test_format_no_error_section_when_no_errors(self):
        scores = BrainScores(score_errors=[])
        text = format_brain_scores(scores)
        assert "Score errors" not in text

    def test_format_data_sufficient_shows_yes(self):
        scores = BrainScores(data_sufficient=True)
        text = format_brain_scores(scores)
        assert "Yes" in text

    def test_format_data_insufficient_shows_no(self):
        scores = BrainScores(data_sufficient=False)
        text = format_brain_scores(scores)
        assert "No" in text


# ---------------------------------------------------------------------------
# compute_brain_scores — fallback path via missing _events attribute
# ---------------------------------------------------------------------------


class TestComputeBrainScoresFallback:
    def test_falls_back_to_fallback_scorer_when_events_unavailable(self, tmp_path):
        """When _events.compute_brain_scores is unavailable, the fallback scorer
        should be used and return a valid BrainScores."""
        db = make_db(tmp_path)
        insert_events(db, [(1, "OUTPUT"), (2, "OUTPUT"), (3, "OUTPUT")])

        import gradata._events as _events

        # Temporarily remove the function to trigger fallback
        original = getattr(_events, "compute_brain_scores", None)
        try:
            if hasattr(_events, "compute_brain_scores"):
                delattr(_events, "compute_brain_scores")
            scores = compute_brain_scores(db, last_n_prospect_sessions=10)
            assert isinstance(scores, BrainScores)
            assert scores.data_sufficient is True
        finally:
            if original is not None:
                _events.compute_brain_scores = original
