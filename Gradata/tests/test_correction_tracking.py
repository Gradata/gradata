"""Tests for scoring/correction_tracking.py — correction analytics and density metrics.

Tests cover:
- compute_half_life: known decaying series → finite half-life
- compute_half_life: flat/growing series → math.inf
- compute_half_life: fewer than 2 non-zero obs → math.inf
- compute_mtbf_mttr: single correction session
- compute_mtbf_mttr: multiple correction sessions with gaps
- compute_mtbf_mttr: consecutive streaks → mttr > 1
- compute_mtbf_mttr: no correction sessions → total_sessions
- _split_half_trend: improving, stable, degrading
- compute_correction_profile from a real SQLite database
- format_correction_profile includes required sections
"""

import json
import math
import sqlite3
from pathlib import Path

import pytest

from gradata.enhancements.scoring.correction_tracking import (
    CorrectionProfile,
    _split_half_trend,
    compute_correction_profile,
    compute_half_life,
    compute_mtbf_mttr,
    format_correction_profile,
)

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def make_events_db(tmp_path: Path) -> Path:
    db = tmp_path / "system.db"
    conn = sqlite3.connect(str(db))
    conn.execute("""
        CREATE TABLE events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session INTEGER,
            type TEXT,
            source TEXT,
            data_json TEXT
        )
    """)
    conn.commit()
    conn.close()
    return db


def insert(db: Path, rows: list[tuple]) -> None:
    """Insert (session, type, data_json) rows. data_json is optional."""
    conn = sqlite3.connect(str(db))
    for row in rows:
        session, typ = row[0], row[1]
        data = row[2] if len(row) > 2 else None
        conn.execute(
            "INSERT INTO events (session, type, data_json) VALUES (?, ?, ?)",
            (session, typ, data),
        )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# compute_half_life
# ---------------------------------------------------------------------------


class TestComputeHalfLife:
    def test_exponentially_decaying_series_returns_finite_half_life(self):
        # d(t) = 1.0 * exp(-0.1*t) — lambda=0.1, half_life = ln2/0.1 ≈ 6.93
        import math

        series = [math.exp(-0.1 * t) for t in range(10)]
        hl = compute_half_life(series)
        assert math.isfinite(hl)
        assert 5.0 < hl < 10.0  # roughly ln2/0.1

    def test_flat_series_returns_inf(self):
        series = [0.5, 0.5, 0.5, 0.5, 0.5]
        hl = compute_half_life(series)
        assert hl == math.inf

    def test_growing_series_returns_inf(self):
        series = [0.1, 0.2, 0.3, 0.4, 0.5]
        hl = compute_half_life(series)
        assert hl == math.inf

    def test_fewer_than_2_points_returns_inf(self):
        assert compute_half_life([]) == math.inf
        assert compute_half_life([0.5]) == math.inf

    def test_all_zero_densities_returns_inf(self):
        assert compute_half_life([0.0, 0.0, 0.0]) == math.inf

    def test_single_nonzero_density_returns_inf(self):
        # Only one non-zero observation — can't fit a line
        assert compute_half_life([0.5, 0.0, 0.0, 0.0]) == math.inf


# ---------------------------------------------------------------------------
# compute_mtbf_mttr
# ---------------------------------------------------------------------------


class TestComputeMtbfMttr:
    def test_no_corrections_returns_total_sessions_and_one(self):
        mtbf, mttr = compute_mtbf_mttr([], total_sessions=10)
        assert mtbf == 10.0
        assert mttr == 1.0

    def test_single_correction_session_mtbf_is_total_sessions(self):
        mtbf, mttr = compute_mtbf_mttr([5], total_sessions=20)
        assert mtbf == 20.0
        assert mttr == 1.0

    def test_two_sessions_gap_3_gives_mtbf_3(self):
        mtbf, _mttr = compute_mtbf_mttr([2, 5], total_sessions=10)
        assert mtbf == pytest.approx(3.0)

    def test_multiple_gaps_averages_correctly(self):
        # Sessions 1, 4, 7 → gaps of 3, 3 → avg mtbf = 3.0
        mtbf, _mttr = compute_mtbf_mttr([1, 4, 7], total_sessions=10)
        assert mtbf == pytest.approx(3.0)

    def test_consecutive_streak_gives_mttr_gt_1(self):
        # Sessions 3, 4, 5 are consecutive → one streak of length 3
        _, mttr = compute_mtbf_mttr([3, 4, 5], total_sessions=10)
        assert mttr == pytest.approx(3.0)

    def test_mixed_streaks_averages_mttr(self):
        # Sessions: 1 (isolated), gap, 4,5 (streak of 2) → streaks=[1,2], avg=1.5
        _, mttr = compute_mtbf_mttr([1, 4, 5], total_sessions=10)
        assert mttr == pytest.approx(1.5)

    def test_deduplicates_duplicate_sessions(self):
        # Duplicates should be removed before computing
        mtbf, _ = compute_mtbf_mttr([3, 3, 6], total_sessions=10)
        # Unique = [3, 6] → gap = 3 → single gap → mtbf = 3.0
        assert mtbf == pytest.approx(3.0)

    def test_zero_total_sessions_returns_zero_mtbf(self):
        mtbf, _mttr = compute_mtbf_mttr([], total_sessions=0)
        # No sessions, no corrections
        assert mtbf == 0.0


# ---------------------------------------------------------------------------
# _split_half_trend
# ---------------------------------------------------------------------------


class TestSplitHalfTrend:
    def test_fewer_than_4_values_is_stable(self):
        trend, pct = _split_half_trend([0.5, 0.4])
        assert trend == "stable"
        assert pct == 0.0

    def test_decreasing_density_is_improving(self):
        # First half avg 0.5, second half avg 0.2 → -60% → improving
        trend, pct = _split_half_trend([0.5, 0.5, 0.2, 0.2])
        assert trend == "improving"
        assert pct < 0.0

    def test_increasing_density_is_degrading(self):
        trend, pct = _split_half_trend([0.2, 0.2, 0.6, 0.6])
        assert trend == "degrading"
        assert pct > 0.0

    def test_within_5pct_is_stable(self):
        # 0.5 → 0.52 is ~4% change, below 5% threshold
        trend, _pct = _split_half_trend([0.50, 0.50, 0.52, 0.52])
        assert trend == "stable"

    def test_zero_baseline_with_positive_recent_returns_100pct(self):
        trend, pct = _split_half_trend([0.0, 0.0, 0.5, 0.5])
        assert pct == 100.0
        assert trend == "degrading"

    def test_zero_baseline_zero_recent_returns_stable(self):
        trend, pct = _split_half_trend([0.0, 0.0, 0.0, 0.0])
        assert trend == "stable"
        assert pct == 0.0


# ---------------------------------------------------------------------------
# compute_correction_profile — database integration
# ---------------------------------------------------------------------------


class TestComputeCorrectionProfile:
    def test_empty_db_returns_zero_profile(self, tmp_path):
        db = make_events_db(tmp_path)
        profile = compute_correction_profile(db, window=20)
        assert profile.total_corrections == 0
        assert profile.total_outputs == 0
        assert profile.correction_rate == 0.0
        assert profile.density_trend == "stable"

    def test_corrections_and_outputs_counted_correctly(self, tmp_path):
        db = make_events_db(tmp_path)
        insert(
            db,
            [
                (1, "CORRECTION"),
                (1, "CORRECTION"),
                (1, "OUTPUT"),
                (2, "OUTPUT"),
                (2, "OUTPUT"),
            ],
        )
        profile = compute_correction_profile(db, window=20)
        assert profile.total_corrections == 2
        assert profile.total_outputs == 3
        assert profile.correction_rate == pytest.approx(2 / 3, abs=0.001)

    def test_category_breakdown_uses_data_json(self, tmp_path):
        db = make_events_db(tmp_path)
        insert(
            db,
            [
                (1, "CORRECTION", json.dumps({"category": "DRAFTING"})),
                (1, "CORRECTION", json.dumps({"category": "ACCURACY"})),
                (1, "CORRECTION", json.dumps({"category": "DRAFTING"})),
            ],
        )
        profile = compute_correction_profile(db, window=20)
        assert profile.category_breakdown["DRAFTING"] == 2
        assert profile.category_breakdown["ACCURACY"] == 1

    def test_missing_category_in_data_json_uses_unknown(self, tmp_path):
        db = make_events_db(tmp_path)
        insert(db, [(1, "CORRECTION", json.dumps({}))])
        profile = compute_correction_profile(db, window=20)
        assert "UNKNOWN" in profile.category_breakdown

    def test_null_data_json_falls_back_to_unknown(self, tmp_path):
        db = make_events_db(tmp_path)
        insert(db, [(1, "CORRECTION", None)])
        profile = compute_correction_profile(db, window=20)
        assert "UNKNOWN" in profile.category_breakdown

    def test_improving_trend_detected(self, tmp_path):
        db = make_events_db(tmp_path)
        # Sessions 1-4: high correction density; sessions 5-8: low density
        # Each session has 1 OUTPUT as denominator
        for s in [1, 2, 3, 4]:
            insert(db, [(s, "CORRECTION"), (s, "OUTPUT")])  # density = 1.0
        for s in [5, 6, 7, 8]:
            insert(db, [(s, "OUTPUT")])  # density = 0.0 (no corrections)
        profile = compute_correction_profile(db, window=20)
        assert profile.density_trend == "improving"

    def test_window_limits_session_range(self, tmp_path):
        db = make_events_db(tmp_path)
        # Sessions 1-5 old; sessions 9-10 recent
        for s in [1, 2, 3, 4, 5]:
            insert(db, [(s, "CORRECTION"), (s, "OUTPUT")])
        insert(db, [(9, "OUTPUT"), (10, "OUTPUT")])
        # With window=2, only sessions 9-10 should be included
        profile = compute_correction_profile(db, window=2)
        # Sessions 9 and 10 have no corrections
        assert profile.total_corrections == 0

    def test_density_per_session_ordered_by_session(self, tmp_path):
        db = make_events_db(tmp_path)
        # Session 1: 1 correction, 1 output (density=1.0)
        # Session 2: 0 corrections, 1 output (density=0.0)
        insert(
            db,
            [
                (1, "CORRECTION"),
                (1, "OUTPUT"),
                (2, "OUTPUT"),
            ],
        )
        profile = compute_correction_profile(db, window=20)
        assert profile.density_per_session[0] == pytest.approx(1.0)
        assert profile.density_per_session[1] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# format_correction_profile
# ---------------------------------------------------------------------------


class TestFormatCorrectionProfile:
    def make_profile(self, **kwargs) -> CorrectionProfile:
        defaults = dict(
            total_corrections=5,
            total_outputs=20,
            correction_rate=0.25,
            density_per_session=[0.3, 0.2, 0.1],
            density_trend="improving",
            density_pct_change=-50.0,
            half_life_sessions=5.0,
            mtbf=3.0,
            mttr=1.5,
            category_breakdown={"DRAFTING": 3, "ACCURACY": 2},
        )
        defaults.update(kwargs)
        return CorrectionProfile(**defaults)

    def test_format_includes_totals(self):
        text = format_correction_profile(self.make_profile())
        assert "5" in text
        assert "20" in text

    def test_format_includes_trend(self):
        text = format_correction_profile(self.make_profile())
        assert "IMPROVING" in text

    def test_format_includes_mtbf_mttr(self):
        text = format_correction_profile(self.make_profile())
        assert "MTBF" in text
        assert "MTTR" in text

    def test_format_inf_half_life_shows_na(self):
        text = format_correction_profile(self.make_profile(half_life_sessions=math.inf))
        assert "N/A" in text

    def test_format_finite_half_life_shows_value(self):
        text = format_correction_profile(self.make_profile(half_life_sessions=7.3))
        assert "7.3" in text

    def test_format_category_breakdown_shown(self):
        text = format_correction_profile(self.make_profile())
        assert "DRAFTING" in text
        assert "ACCURACY" in text

    def test_format_no_categories_excludes_section(self):
        text = format_correction_profile(self.make_profile(category_breakdown={}))
        assert "Categories:" not in text

    def test_format_recent_densities_shown(self):
        text = format_correction_profile(self.make_profile())
        assert "Recent densities" in text

    def test_format_no_densities_excludes_recent_section(self):
        text = format_correction_profile(self.make_profile(density_per_session=[]))
        assert "Recent densities" not in text
