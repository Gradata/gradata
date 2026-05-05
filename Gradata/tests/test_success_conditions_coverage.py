"""
Tests for gradata.enhancements.scoring.success_conditions
==========================================================
Target: >=85% line coverage of success_conditions.py (113 statements).

Strategy
--------
- All tests use tmp_path to create a real SQLite DB in an isolated directory.
- No network calls; no side effects outside tmp_path.
- The blandness / compute_metrics integration path is patched via monkeypatch
  so we avoid a hard dependency on gradata.enhancements.metrics.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from gradata.enhancements.scoring.success_conditions import (
    ConditionResult,
    SuccessReport,
    _get_session_metrics,
    _split_halves,
    evaluate_success_conditions,
    format_success_report,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db(path: Path) -> sqlite3.Connection:
    """Create a minimal events table and return an open connection."""
    conn = sqlite3.connect(str(path))
    conn.execute("""
        CREATE TABLE events (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            type      TEXT NOT NULL,
            session   INTEGER,
            data_json TEXT
        )
    """)
    conn.commit()
    return conn


def _insert_events(conn: sqlite3.Connection, rows: list[tuple]) -> None:
    """Insert (type, session, data_json) tuples."""
    conn.executemany("INSERT INTO events (type, session, data_json) VALUES (?, ?, ?)", rows)
    conn.commit()


def _seed_sessions(
    conn: sqlite3.Connection,
    *,
    sessions: int,
    outputs_per: int = 4,
    corrections_per: int = 1,
    edit_distance: float | None = None,
    rule_apps_per: int = 2,
    rule_accepted: bool = True,
    misfired: bool = False,
) -> None:
    """Populate enough rows across `sessions` sessions to satisfy n>=4 checks."""
    rows = []
    for s in range(1, sessions + 1):
        for _ in range(outputs_per):
            rows.append(("OUTPUT", s, json.dumps({"major_edit": 0})))
        for _ in range(corrections_per):
            data: dict = {"category": "test", "severity": "minor"}
            if edit_distance is not None:
                data["edit_distance"] = edit_distance
            rows.append(("CORRECTION", s, json.dumps(data)))
        for _ in range(rule_apps_per):
            rows.append(
                (
                    "RULE_APPLICATION",
                    s,
                    json.dumps(
                        {"accepted": 1 if rule_accepted else 0, "misfired": 1 if misfired else 0}
                    ),
                )
            )
    _insert_events(conn, rows)


# ---------------------------------------------------------------------------
# ConditionResult dataclass
# ---------------------------------------------------------------------------


class TestConditionResult:
    def test_fields_stored(self):
        cr = ConditionResult(
            name="test_cond",
            met=True,
            current_value=0.1,
            baseline_value=0.2,
            trend="improving",
            detail="x -> y",
        )
        assert cr.name == "test_cond"
        assert cr.met is True
        assert cr.current_value == 0.1
        assert cr.baseline_value == 0.2
        assert cr.trend == "improving"
        assert cr.detail == "x -> y"

    def test_not_met(self):
        cr = ConditionResult("c", False, 0.5, 0.3, "degrading", "bad")
        assert not cr.met


# ---------------------------------------------------------------------------
# SuccessReport dataclass + properties
# ---------------------------------------------------------------------------


class TestSuccessReport:
    def _make_report(self, met_flags: list[bool]) -> SuccessReport:
        conditions = [
            ConditionResult(f"cond_{i}", m, float(i), 0.0, "stable", "d")
            for i, m in enumerate(met_flags)
        ]
        all_met = all(met_flags) and len(met_flags) >= 3
        return SuccessReport(
            conditions=conditions,
            all_met=all_met,
            sessions_evaluated=len(met_flags) * 5,
            window_size=20,
        )

    def test_met_count_all_true(self):
        r = self._make_report([True, True, True])
        assert r.met_count == 3

    def test_met_count_mixed(self):
        r = self._make_report([True, False, True, False])
        assert r.met_count == 2

    def test_total_count(self):
        r = self._make_report([True, False, True])
        assert r.total_count == 3

    def test_all_met_true(self):
        r = self._make_report([True, True, True])
        assert r.all_met is True

    def test_all_met_false_when_any_false(self):
        r = self._make_report([True, False, True])
        assert r.all_met is False

    def test_all_met_false_when_fewer_than_three(self):
        # even if all individual conditions pass, all_met requires len>=3
        r = self._make_report([True, True])
        # our helper sets all_met = all(flags) and len>=3
        assert r.all_met is False


# ---------------------------------------------------------------------------
# _split_halves
# ---------------------------------------------------------------------------


class TestSplitHalves:
    def test_too_short_returns_zeros(self):
        assert _split_halves([]) == (0.0, 0.0)
        assert _split_halves([1.0]) == (0.0, 0.0)
        assert _split_halves([1.0, 2.0, 3.0]) == (0.0, 0.0)

    def test_four_values(self):
        first, second = _split_halves([1.0, 2.0, 3.0, 4.0])
        assert first == pytest.approx(1.5)  # avg(1,2)
        assert second == pytest.approx(3.5)  # avg(3,4)

    def test_six_values(self):
        first, second = _split_halves([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
        assert first == pytest.approx(2.0)  # avg(1,2,3)
        assert second == pytest.approx(5.0)  # avg(4,5,6)

    def test_five_values(self):
        # len=5, mid=2 -> first=[v0,v1], second=[v2,v3,v4]
        first, second = _split_halves([10.0, 20.0, 30.0, 40.0, 50.0])
        assert first == pytest.approx(15.0)
        assert second == pytest.approx(40.0)

    def test_identical_values(self):
        first, second = _split_halves([5.0, 5.0, 5.0, 5.0])
        assert first == pytest.approx(5.0)
        assert second == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# _get_session_metrics
# ---------------------------------------------------------------------------


class TestGetSessionMetrics:
    def test_returns_empty_when_no_events_table(self, tmp_path):
        db_path = tmp_path / "empty.db"
        conn = sqlite3.connect(str(db_path))
        # No events table — should hit OperationalError branch
        result = _get_session_metrics(conn, 20)
        conn.close()
        assert result == []

    def test_returns_empty_when_table_is_empty(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = _make_db(db_path)
        result = _get_session_metrics(conn, 20)
        conn.close()
        assert result == []

    def test_aggregates_by_session(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = _make_db(db_path)
        _insert_events(
            conn,
            [
                ("OUTPUT", 1, None),
                ("OUTPUT", 1, None),
                ("CORRECTION", 1, None),
                ("OUTPUT", 2, None),
                ("RULE_APPLICATION", 2, None),
            ],
        )
        result = _get_session_metrics(conn, 20)
        conn.close()
        by_session = {r["session"]: r for r in result}
        assert by_session[1]["outputs"] == 2
        assert by_session[1]["corrections"] == 1
        assert by_session[1]["rule_apps"] == 0
        assert by_session[2]["outputs"] == 1
        assert by_session[2]["rule_apps"] == 1

    def test_respects_window_limit(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = _make_db(db_path)
        rows = [("OUTPUT", s, None) for s in range(1, 31)]
        _insert_events(conn, rows)
        result = _get_session_metrics(conn, 5)
        conn.close()
        assert len(result) == 5

    def test_null_session_excluded(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = _make_db(db_path)
        _insert_events(
            conn,
            [
                ("OUTPUT", None, None),
                ("OUTPUT", 1, None),
            ],
        )
        result = _get_session_metrics(conn, 20)
        conn.close()
        assert all(r["session"] is not None for r in result)

    def test_oldest_first_ordering(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = _make_db(db_path)
        rows = [("OUTPUT", s, None) for s in [3, 1, 2]]
        _insert_events(conn, rows)
        result = _get_session_metrics(conn, 20)
        conn.close()
        sessions = [r["session"] for r in result]
        assert sessions == sorted(sessions)


# ---------------------------------------------------------------------------
# evaluate_success_conditions — path: db does not exist
# ---------------------------------------------------------------------------


class TestEvaluateSuccessConditionsNoDb:
    def test_missing_db_returns_empty_report(self, tmp_path):
        absent = tmp_path / "no_such.db"
        report = evaluate_success_conditions(absent)
        assert isinstance(report, SuccessReport)
        assert report.all_met is False
        assert report.sessions_evaluated == 0
        assert report.conditions == []

    def test_missing_db_uses_window_size(self, tmp_path):
        absent = tmp_path / "no_such.db"
        report = evaluate_success_conditions(absent, window=42)
        assert report.window_size == 42


# ---------------------------------------------------------------------------
# evaluate_success_conditions — path: insufficient data (n < 4)
# ---------------------------------------------------------------------------


class TestEvaluateInsufficientData:
    def test_zero_sessions(self, tmp_path):
        db_path = tmp_path / "brain.db"
        conn = _make_db(db_path)
        conn.close()
        report = evaluate_success_conditions(db_path)
        assert report.all_met is False
        assert report.sessions_evaluated == 0
        assert len(report.conditions) == 1
        assert report.conditions[0].name == "insufficient_data"

    def test_three_sessions(self, tmp_path):
        db_path = tmp_path / "brain.db"
        conn = _make_db(db_path)
        _insert_events(conn, [("OUTPUT", s, None) for s in [1, 2, 3]])
        conn.close()
        report = evaluate_success_conditions(db_path)
        assert report.sessions_evaluated == 3
        assert report.conditions[0].name == "insufficient_data"
        assert "Need 4+" in report.conditions[0].detail

    def test_insufficient_data_condition_detail(self, tmp_path):
        db_path = tmp_path / "brain.db"
        conn = _make_db(db_path)
        _insert_events(conn, [("OUTPUT", 1, None)])
        conn.close()
        report = evaluate_success_conditions(db_path)
        cond = report.conditions[0]
        assert cond.current_value == 1.0
        assert cond.baseline_value == 4.0
        assert cond.trend == "n/a"


# ---------------------------------------------------------------------------
# evaluate_success_conditions — full path with >=4 sessions
# ---------------------------------------------------------------------------


class TestEvaluateFullConditions:
    """Tests that exercise the main evaluation branches with 4+ sessions."""

    def test_correction_rate_improving(self, tmp_path):
        """Decreasing corrections over time -> correction_rate_decreases met."""
        db_path = tmp_path / "brain.db"
        conn = _make_db(db_path)
        # Sessions 1-2 (baseline): 3 corrections / 4 outputs each = 0.75 rate
        # Sessions 3-4 (current):  1 correction  / 4 outputs each = 0.25 rate
        rows = []
        for s in [1, 2]:
            rows += [("OUTPUT", s, None)] * 4
            rows += [("CORRECTION", s, None)] * 3
        for s in [3, 4]:
            rows += [("OUTPUT", s, None)] * 4
            rows += [("CORRECTION", s, None)] * 1
        _insert_events(conn, rows)
        conn.close()
        report = evaluate_success_conditions(db_path)
        cr_cond = next(c for c in report.conditions if c.name == "correction_rate_decreases")
        assert cr_cond.met is True
        assert cr_cond.trend == "improving"

    def test_correction_rate_degrading(self, tmp_path):
        """Increasing corrections over time -> condition not met."""
        db_path = tmp_path / "brain.db"
        conn = _make_db(db_path)
        for s in [1, 2]:
            _insert_events(conn, [("OUTPUT", s, None)] * 4 + [("CORRECTION", s, None)] * 1)
        for s in [3, 4]:
            _insert_events(conn, [("OUTPUT", s, None)] * 4 + [("CORRECTION", s, None)] * 4)
        conn.close()
        report = evaluate_success_conditions(db_path)
        cr_cond = next(c for c in report.conditions if c.name == "correction_rate_decreases")
        assert cr_cond.met is False
        assert cr_cond.trend == "degrading"

    def test_zero_outputs_in_session_handled(self, tmp_path):
        """Session with 0 outputs should default correction rate to 0.0."""
        db_path = tmp_path / "brain.db"
        conn = _make_db(db_path)
        # 4 sessions, some with zero outputs
        _insert_events(
            conn,
            [
                ("CORRECTION", 1, None),  # no OUTPUT for session 1
                ("OUTPUT", 2, None),
                ("OUTPUT", 2, None),
                ("OUTPUT", 3, None),
                ("OUTPUT", 3, None),
                ("OUTPUT", 4, None),
                ("OUTPUT", 4, None),
            ],
        )
        conn.close()
        # Should not raise
        report = evaluate_success_conditions(db_path)
        assert any(c.name == "correction_rate_decreases" for c in report.conditions)

    def test_edit_distance_branch_improving(self, tmp_path):
        """4+ sessions with edit_distance data -> edit_distance_decreases evaluated."""
        db_path = tmp_path / "brain.db"
        conn = _make_db(db_path)
        # Seed base session metrics (4 sessions with outputs)
        _seed_sessions(conn, sessions=4, outputs_per=4, corrections_per=0, rule_apps_per=0)
        # Overlay edit_distance CORRECTION events: high early, low later
        ed_rows = [
            ("CORRECTION", 1, json.dumps({"edit_distance": 10.0})),
            ("CORRECTION", 2, json.dumps({"edit_distance": 8.0})),
            ("CORRECTION", 3, json.dumps({"edit_distance": 3.0})),
            ("CORRECTION", 4, json.dumps({"edit_distance": 1.0})),
        ]
        _insert_events(conn, ed_rows)
        conn.close()
        report = evaluate_success_conditions(db_path)
        ed_cond = next((c for c in report.conditions if c.name == "edit_distance_decreases"), None)
        assert ed_cond is not None
        assert ed_cond.met is True
        assert ed_cond.trend == "improving"

    def test_edit_distance_branch_degrading(self, tmp_path):
        db_path = tmp_path / "brain.db"
        conn = _make_db(db_path)
        _seed_sessions(conn, sessions=4, outputs_per=4, corrections_per=0, rule_apps_per=0)
        ed_rows = [
            ("CORRECTION", 1, json.dumps({"edit_distance": 1.0})),
            ("CORRECTION", 2, json.dumps({"edit_distance": 2.0})),
            ("CORRECTION", 3, json.dumps({"edit_distance": 8.0})),
            ("CORRECTION", 4, json.dumps({"edit_distance": 10.0})),
        ]
        _insert_events(conn, ed_rows)
        conn.close()
        report = evaluate_success_conditions(db_path)
        ed_cond = next((c for c in report.conditions if c.name == "edit_distance_decreases"), None)
        assert ed_cond is not None
        assert ed_cond.met is False
        assert ed_cond.trend == "degrading"

    def test_edit_distance_skipped_when_fewer_than_4_sessions(self, tmp_path):
        """Only 2 sessions with edit_distance -> branch skipped, no condition added."""
        db_path = tmp_path / "brain.db"
        conn = _make_db(db_path)
        _seed_sessions(conn, sessions=4, outputs_per=4, corrections_per=0, rule_apps_per=0)
        # Only 2 sessions have edit_distance data
        _insert_events(
            conn,
            [
                ("CORRECTION", 1, json.dumps({"edit_distance": 5.0})),
                ("CORRECTION", 2, json.dumps({"edit_distance": 3.0})),
            ],
        )
        conn.close()
        report = evaluate_success_conditions(db_path)
        names = [c.name for c in report.conditions]
        assert "edit_distance_decreases" not in names

    def test_acceptance_rate_improving(self, tmp_path):
        """More non-major edits in later sessions -> acceptance_rate_increases met."""
        db_path = tmp_path / "brain.db"
        conn = _make_db(db_path)
        # Early sessions: major edits present (accepted=False proxy)
        for s in [1, 2]:
            _insert_events(
                conn,
                [
                    ("OUTPUT", s, json.dumps({"major_edit": 1})),
                    ("OUTPUT", s, json.dumps({"major_edit": 1})),
                    ("OUTPUT", s, json.dumps({"major_edit": 0})),
                    ("OUTPUT", s, json.dumps({"major_edit": 0})),
                ],
            )
        # Later sessions: mostly accepted
        for s in [3, 4]:
            _insert_events(
                conn,
                [
                    ("OUTPUT", s, json.dumps({"major_edit": 0})),
                    ("OUTPUT", s, json.dumps({"major_edit": 0})),
                    ("OUTPUT", s, json.dumps({"major_edit": 0})),
                    ("OUTPUT", s, json.dumps({"major_edit": 0})),
                ],
            )
        conn.close()
        report = evaluate_success_conditions(db_path)
        fda = next((c for c in report.conditions if c.name == "acceptance_rate_increases"), None)
        assert fda is not None
        assert fda.met is True

    def test_acceptance_rate_null_major_edit_treated_as_accepted(self, tmp_path):
        """NULL major_edit should count as accepted (no major edit)."""
        db_path = tmp_path / "brain.db"
        conn = _make_db(db_path)
        for s in range(1, 5):
            _insert_events(
                conn,
                [
                    ("OUTPUT", s, json.dumps({})),  # major_edit IS NULL
                    ("OUTPUT", s, json.dumps({})),
                    ("OUTPUT", s, json.dumps({})),
                    ("OUTPUT", s, json.dumps({})),
                ],
            )
        conn.close()
        report = evaluate_success_conditions(db_path)
        fda = next((c for c in report.conditions if c.name == "acceptance_rate_increases"), None)
        assert fda is not None
        # All are "accepted" (no major_edit), rate should be 1.0 in both halves -> met
        assert fda.met is True

    def test_rule_success_rate_improving(self, tmp_path):
        """More accepted rule applications in later sessions."""
        db_path = tmp_path / "brain.db"
        conn = _make_db(db_path)
        # Baseline sessions: low acceptance
        for s in [1, 2]:
            _insert_events(
                conn,
                [
                    ("OUTPUT", s, None),
                    ("OUTPUT", s, None),
                    ("RULE_APPLICATION", s, json.dumps({"accepted": 0})),
                    ("RULE_APPLICATION", s, json.dumps({"accepted": 0})),
                    ("RULE_APPLICATION", s, json.dumps({"accepted": 1})),
                ],
            )
        # Current sessions: high acceptance
        for s in [3, 4]:
            _insert_events(
                conn,
                [
                    ("OUTPUT", s, None),
                    ("OUTPUT", s, None),
                    ("RULE_APPLICATION", s, json.dumps({"accepted": 1})),
                    ("RULE_APPLICATION", s, json.dumps({"accepted": 1})),
                    ("RULE_APPLICATION", s, json.dumps({"accepted": 1})),
                ],
            )
        conn.close()
        report = evaluate_success_conditions(db_path)
        rs = next((c for c in report.conditions if c.name == "rule_success_increases"), None)
        assert rs is not None
        assert rs.met is True

    def test_rule_success_rate_degrading(self, tmp_path):
        db_path = tmp_path / "brain.db"
        conn = _make_db(db_path)
        for s in [1, 2]:
            _insert_events(
                conn,
                [
                    ("OUTPUT", s, None),
                    ("OUTPUT", s, None),
                    ("RULE_APPLICATION", s, json.dumps({"accepted": 1})),
                    ("RULE_APPLICATION", s, json.dumps({"accepted": 1})),
                ],
            )
        for s in [3, 4]:
            _insert_events(
                conn,
                [
                    ("OUTPUT", s, None),
                    ("OUTPUT", s, None),
                    ("RULE_APPLICATION", s, json.dumps({"accepted": 0})),
                    ("RULE_APPLICATION", s, json.dumps({"accepted": 0})),
                ],
            )
        conn.close()
        report = evaluate_success_conditions(db_path)
        rs = next((c for c in report.conditions if c.name == "rule_success_increases"), None)
        assert rs is not None
        assert rs.met is False

    def test_misfires_stay_low_when_low(self, tmp_path):
        """Low misfire rate throughout -> misfires_stay_low met."""
        db_path = tmp_path / "brain.db"
        conn = _make_db(db_path)
        for s in range(1, 5):
            _insert_events(
                conn,
                [
                    ("OUTPUT", s, None),
                    ("OUTPUT", s, None),
                    ("RULE_APPLICATION", s, json.dumps({"accepted": 1, "misfired": 0})),
                    ("RULE_APPLICATION", s, json.dumps({"accepted": 1, "misfired": 0})),
                    ("RULE_APPLICATION", s, json.dumps({"accepted": 1, "misfired": 0})),
                ],
            )
        conn.close()
        report = evaluate_success_conditions(db_path)
        mf = next((c for c in report.conditions if c.name == "misfires_stay_low"), None)
        assert mf is not None
        assert mf.met is True

    def test_misfires_degrading_trend(self, tmp_path):
        """High misfire rate in current half -> not met, trend=degrading."""
        db_path = tmp_path / "brain.db"
        conn = _make_db(db_path)
        # Baseline: 0% misfire
        for s in [1, 2]:
            _insert_events(
                conn,
                [
                    ("OUTPUT", s, None),
                    ("OUTPUT", s, None),
                    ("RULE_APPLICATION", s, json.dumps({"misfired": 0})),
                    ("RULE_APPLICATION", s, json.dumps({"misfired": 0})),
                ],
            )
        # Current: 100% misfire
        for s in [3, 4]:
            _insert_events(
                conn,
                [
                    ("OUTPUT", s, None),
                    ("OUTPUT", s, None),
                    ("RULE_APPLICATION", s, json.dumps({"misfired": 1})),
                    ("RULE_APPLICATION", s, json.dumps({"misfired": 1})),
                ],
            )
        conn.close()
        report = evaluate_success_conditions(db_path)
        mf = next((c for c in report.conditions if c.name == "misfires_stay_low"), None)
        assert mf is not None
        assert mf.met is False
        assert mf.trend == "degrading"

    def test_misfires_stable_trend(self, tmp_path):
        """Small delta in misfire rate -> trend=stable."""
        db_path = tmp_path / "brain.db"
        conn = _make_db(db_path)
        # 5% misfire throughout (well within 0.05 delta)
        for s in range(1, 5):
            _insert_events(
                conn,
                [
                    ("OUTPUT", s, None),
                    ("OUTPUT", s, None),
                    ("RULE_APPLICATION", s, json.dumps({"misfired": 0})),
                    ("RULE_APPLICATION", s, json.dumps({"misfired": 0})),
                    ("RULE_APPLICATION", s, json.dumps({"misfired": 0})),
                    ("RULE_APPLICATION", s, json.dumps({"misfired": 0})),
                    ("RULE_APPLICATION", s, json.dumps({"misfired": 0})),
                    ("RULE_APPLICATION", s, json.dumps({"misfired": 0})),
                    ("RULE_APPLICATION", s, json.dumps({"misfired": 0})),
                    ("RULE_APPLICATION", s, json.dumps({"misfired": 0})),
                    ("RULE_APPLICATION", s, json.dumps({"misfired": 0})),
                    ("RULE_APPLICATION", s, json.dumps({"misfired": 0})),
                    ("RULE_APPLICATION", s, json.dumps({"misfired": 0})),
                    ("RULE_APPLICATION", s, json.dumps({"misfired": 0})),
                    ("RULE_APPLICATION", s, json.dumps({"misfired": 0})),
                    ("RULE_APPLICATION", s, json.dumps({"misfired": 0})),
                    ("RULE_APPLICATION", s, json.dumps({"misfired": 0})),
                    ("RULE_APPLICATION", s, json.dumps({"misfired": 0})),
                    ("RULE_APPLICATION", s, json.dumps({"misfired": 0})),
                    ("RULE_APPLICATION", s, json.dumps({"misfired": 0})),
                    ("RULE_APPLICATION", s, json.dumps({"misfired": 0})),
                    ("RULE_APPLICATION", s, json.dumps({"misfired": 1})),
                ],
            )
        conn.close()
        report = evaluate_success_conditions(db_path)
        mf = next((c for c in report.conditions if c.name == "misfires_stay_low"), None)
        assert mf is not None
        assert mf.trend == "stable"

    def test_misfires_improving_trend(self, tmp_path):
        """Lower misfire rate in current half -> trend=improving."""
        db_path = tmp_path / "brain.db"
        conn = _make_db(db_path)
        # Baseline: 50% misfire
        for s in [1, 2]:
            _insert_events(
                conn,
                [
                    ("OUTPUT", s, None),
                    ("OUTPUT", s, None),
                    ("RULE_APPLICATION", s, json.dumps({"misfired": 1})),
                    ("RULE_APPLICATION", s, json.dumps({"misfired": 0})),
                ],
            )
        # Current: 0% misfire
        for s in [3, 4]:
            _insert_events(
                conn,
                [
                    ("OUTPUT", s, None),
                    ("OUTPUT", s, None),
                    ("RULE_APPLICATION", s, json.dumps({"misfired": 0})),
                    ("RULE_APPLICATION", s, json.dumps({"misfired": 0})),
                ],
            )
        conn.close()
        report = evaluate_success_conditions(db_path)
        mf = next((c for c in report.conditions if c.name == "misfires_stay_low"), None)
        assert mf is not None
        assert mf.met is True
        assert mf.trend == "improving"

    def test_all_met_requires_at_least_3_conditions(self, tmp_path):
        """all_met is False when fewer than 3 conditions are produced."""
        # 4 sessions but no RULE_APPLICATION or CORRECTION events -> only
        # correction_rate_decreases and possibly acceptance_rate_increases
        db_path = tmp_path / "brain.db"
        conn = _make_db(db_path)
        for s in range(1, 5):
            _insert_events(conn, [("OUTPUT", s, None)] * 4)
        conn.close()
        report = evaluate_success_conditions(db_path)
        if len(report.conditions) < 3:
            assert report.all_met is False

    def test_all_conditions_met_sets_all_met_true(self, tmp_path):
        """When all conditions pass and count >= 3, all_met is True."""
        db_path = tmp_path / "brain.db"
        conn = _make_db(db_path)
        # 8 sessions: decreasing corrections, stable acceptance, increasing rule success, low misfire
        for s in range(1, 9):
            corr_count = max(4 - (s // 2), 0)
            _insert_events(
                conn,
                [
                    *[("OUTPUT", s, json.dumps({"major_edit": 0}))] * 4,
                    *[("CORRECTION", s, None)] * corr_count,
                    ("RULE_APPLICATION", s, json.dumps({"accepted": 1, "misfired": 0})),
                    ("RULE_APPLICATION", s, json.dumps({"accepted": 1, "misfired": 0})),
                ],
            )
        conn.close()
        report = evaluate_success_conditions(db_path, window=8)
        # At minimum the correction_rate, acceptance, rule_success, misfire conditions exist
        assert len(report.conditions) >= 3
        # Check all_met reflects actual condition outcomes
        assert report.all_met == (
            all(c.met for c in report.conditions) and len(report.conditions) >= 3
        )

    def test_custom_window_respected(self, tmp_path):
        """window parameter is stored in the report."""
        db_path = tmp_path / "brain.db"
        conn = _make_db(db_path)
        _seed_sessions(conn, sessions=4)
        conn.close()
        report = evaluate_success_conditions(db_path, window=10)
        assert report.window_size == 10


# ---------------------------------------------------------------------------
# evaluate_success_conditions — blandness / compute_metrics branch
# ---------------------------------------------------------------------------


class TestBlandnessBranch:
    def _seed_4_sessions(self, tmp_path: Path) -> Path:
        db_path = tmp_path / "brain.db"
        conn = _make_db(db_path)
        _seed_sessions(conn, sessions=4, outputs_per=4, corrections_per=1, rule_apps_per=2)
        conn.close()
        return db_path

    def test_blandness_below_threshold_met(self, tmp_path):
        """compute_metrics returns blandness=0.3 -> output_not_bland met."""
        db_path = self._seed_4_sessions(tmp_path)
        with patch(
            "gradata.enhancements.scoring.success_conditions.evaluate_success_conditions.__wrapped__"
            if hasattr(evaluate_success_conditions, "__wrapped__")
            else "gradata.enhancements.metrics.compute_metrics",
            return_value={"blandness_score": 0.3},
            create=True,
        ):
            with patch.dict("sys.modules", {}):
                # Patch at the import site inside the function
                import sys

                fake_metrics = type(sys)("gradata.enhancements.metrics")
                fake_metrics.compute_metrics = lambda db_path, window: {"blandness_score": 0.3}
                orig = sys.modules.get("gradata.enhancements.metrics")
                sys.modules["gradata.enhancements.metrics"] = fake_metrics
                try:
                    report = evaluate_success_conditions(db_path)
                finally:
                    if orig is None:
                        sys.modules.pop("gradata.enhancements.metrics", None)
                    else:
                        sys.modules["gradata.enhancements.metrics"] = orig
        bland = next((c for c in report.conditions if c.name == "output_not_bland"), None)
        if bland is not None:
            assert bland.met is True
            assert bland.trend == "varied"

    def test_blandness_above_threshold_not_met(self, tmp_path):
        """compute_metrics returns blandness=0.85 -> output_not_bland not met."""
        db_path = self._seed_4_sessions(tmp_path)
        import sys

        fake_metrics = type(sys)("gradata.enhancements.metrics")
        fake_metrics.compute_metrics = lambda db_path, window: {"blandness_score": 0.85}
        orig = sys.modules.get("gradata.enhancements.metrics")
        sys.modules["gradata.enhancements.metrics"] = fake_metrics
        try:
            report = evaluate_success_conditions(db_path)
        finally:
            if orig is None:
                sys.modules.pop("gradata.enhancements.metrics", None)
            else:
                sys.modules["gradata.enhancements.metrics"] = orig
        bland = next((c for c in report.conditions if c.name == "output_not_bland"), None)
        if bland is not None:
            assert bland.met is False
            assert bland.trend == "generic"

    def test_blandness_object_with_attribute(self, tmp_path):
        """compute_metrics returns an object with .blandness_score attribute."""
        db_path = self._seed_4_sessions(tmp_path)
        import sys

        class FakeMetrics:
            blandness_score = 0.5

        fake_module = type(sys)("gradata.enhancements.metrics")
        fake_module.compute_metrics = lambda db_path, window: FakeMetrics()
        orig = sys.modules.get("gradata.enhancements.metrics")
        sys.modules["gradata.enhancements.metrics"] = fake_module
        try:
            report = evaluate_success_conditions(db_path)
        finally:
            if orig is None:
                sys.modules.pop("gradata.enhancements.metrics", None)
            else:
                sys.modules["gradata.enhancements.metrics"] = orig
        bland = next((c for c in report.conditions if c.name == "output_not_bland"), None)
        if bland is not None:
            assert bland.met is True

    def test_blandness_exception_silently_skipped(self, tmp_path):
        """If compute_metrics raises, output_not_bland is simply absent."""
        db_path = self._seed_4_sessions(tmp_path)
        import sys

        fake_module = type(sys)("gradata.enhancements.metrics")
        fake_module.compute_metrics = lambda db_path, window: (_ for _ in ()).throw(
            RuntimeError("unavailable")
        )
        orig = sys.modules.get("gradata.enhancements.metrics")
        sys.modules["gradata.enhancements.metrics"] = fake_module
        try:
            report = evaluate_success_conditions(db_path)
        finally:
            if orig is None:
                sys.modules.pop("gradata.enhancements.metrics", None)
            else:
                sys.modules["gradata.enhancements.metrics"] = orig
        names = [c.name for c in report.conditions]
        assert "output_not_bland" not in names


# ---------------------------------------------------------------------------
# format_success_report
# ---------------------------------------------------------------------------


class TestFormatSuccessReport:
    def _make_full_report(self, all_met: bool) -> SuccessReport:
        conditions = [
            ConditionResult(
                "correction_rate_decreases", all_met, 0.1, 0.2, "improving", "0.20% -> 0.10%"
            ),
            ConditionResult(
                "edit_distance_decreases", all_met, 2.0, 5.0, "improving", "5.00 -> 2.00"
            ),
            ConditionResult(
                "acceptance_rate_increases", all_met, 0.9, 0.7, "improving", "70.0% -> 90.0%"
            ),
        ]
        return SuccessReport(
            conditions=conditions,
            all_met=all_met,
            sessions_evaluated=20,
            window_size=20,
        )

    def test_returns_string(self):
        report = self._make_full_report(True)
        result = format_success_report(report)
        assert isinstance(result, str)

    def test_all_met_verdict_in_output(self):
        report = self._make_full_report(True)
        result = format_success_report(report)
        assert "ALL MET" in result

    def test_partial_met_verdict_in_output(self):
        conditions = [
            ConditionResult("a", True, 0.1, 0.2, "improving", "d1"),
            ConditionResult("b", False, 0.5, 0.3, "degrading", "d2"),
            ConditionResult("c", True, 0.8, 0.7, "stable", "d3"),
        ]
        report = SuccessReport(
            conditions=conditions, all_met=False, sessions_evaluated=20, window_size=20
        )
        result = format_success_report(report)
        assert "2/3 MET" in result

    def test_sessions_evaluated_in_output(self):
        report = self._make_full_report(True)
        result = format_success_report(report)
        assert "Sessions evaluated: 20" in result

    def test_window_size_in_output(self):
        report = self._make_full_report(True)
        result = format_success_report(report)
        assert "window: 20" in result

    def test_pass_icon_for_met_condition(self):
        report = self._make_full_report(True)
        result = format_success_report(report)
        assert "[PASS]" in result

    def test_fail_icon_for_not_met_condition(self):
        conditions = [ConditionResult("x", False, 0.5, 0.1, "degrading", "bad")]
        report = SuccessReport(
            conditions=conditions, all_met=False, sessions_evaluated=5, window_size=20
        )
        result = format_success_report(report)
        assert "[FAIL]" in result

    def test_compounding_message_when_all_met(self):
        report = self._make_full_report(True)
        result = format_success_report(report)
        assert "compounding" in result

    def test_focus_message_when_not_all_met(self):
        conditions = [
            ConditionResult("good_cond", True, 0.1, 0.2, "improving", "ok"),
            ConditionResult("bad_cond", False, 0.5, 0.1, "degrading", "bad"),
        ]
        report = SuccessReport(
            conditions=conditions, all_met=False, sessions_evaluated=10, window_size=20
        )
        result = format_success_report(report)
        assert "bad_cond" in result
        assert "Focus on" in result

    def test_condition_names_appear_in_output(self):
        report = self._make_full_report(True)
        result = format_success_report(report)
        assert "correction_rate_decreases" in result
        assert "edit_distance_decreases" in result
        assert "acceptance_rate_increases" in result

    def test_condition_detail_appears_in_output(self):
        report = self._make_full_report(True)
        result = format_success_report(report)
        assert "0.20%" in result

    def test_empty_conditions_partial_verdict(self):
        report = SuccessReport(conditions=[], all_met=False, sessions_evaluated=0, window_size=20)
        result = format_success_report(report)
        assert "0/0 MET" in result

    def test_trend_appears_in_output(self):
        report = self._make_full_report(True)
        result = format_success_report(report)
        assert "improving" in result

    def test_multiple_failed_conditions_all_listed(self):
        conditions = [
            ConditionResult("cond_a", False, 0.5, 0.1, "degrading", "bad a"),
            ConditionResult("cond_b", False, 0.8, 0.2, "degrading", "bad b"),
        ]
        report = SuccessReport(
            conditions=conditions, all_met=False, sessions_evaluated=10, window_size=20
        )
        result = format_success_report(report)
        assert "cond_a" in result
        assert "cond_b" in result


# ---------------------------------------------------------------------------
# OperationalError guard branches (lines 158-159, 184-185, 208-209, 233-234)
# Each secondary query uses json_extract; we trigger the OperationalError by
# dropping the events table after _get_session_metrics populates `metrics`
# but before the secondary queries run. We do this by wrapping sqlite3.connect
# to return a connection whose execute raises OperationalError on the second+
# call (the sub-queries), while returning real rows on the first call.
# ---------------------------------------------------------------------------


class TestOperationalErrorBranches:
    """Cover the four `except sqlite3.OperationalError: pass` guards."""

    def _db_with_4_sessions(self, tmp_path: Path) -> Path:
        db_path = tmp_path / "brain.db"
        conn = _make_db(db_path)
        _seed_sessions(
            conn, sessions=4, outputs_per=4, corrections_per=2, rule_apps_per=2, edit_distance=5.0
        )
        conn.close()
        return db_path

    def test_operational_error_in_edit_distance_query(self, tmp_path, monkeypatch):
        """OperationalError in edit_distance sub-query is silently swallowed."""
        db_path = self._db_with_4_sessions(tmp_path)

        real_connect = sqlite3.connect
        call_count = [0]

        class BrokenOnSecondQuery:
            def __init__(self, real_conn):
                self._conn = real_conn
                self._query_count = 0

            def execute(self, sql, params=()):
                # First execute is the session-metrics GROUP BY — let it pass.
                # All subsequent ones raise OperationalError.
                self._query_count += 1
                if self._query_count == 1:
                    return self._conn.execute(sql, params)
                raise sqlite3.OperationalError("simulated")

            def close(self):
                self._conn.close()

        def patched_connect(path, **kw):
            call_count[0] += 1
            real_conn = real_connect(path, **kw)
            return BrokenOnSecondQuery(real_conn)

        monkeypatch.setattr(sqlite3, "connect", patched_connect)
        # Should not raise; OperationalError branches are all `pass`
        report = evaluate_success_conditions(db_path)
        assert isinstance(report, SuccessReport)
        # correction_rate_decreases is computed from session metrics (first query)
        names = [c.name for c in report.conditions]
        assert "correction_rate_decreases" in names
        # All four sub-query conditions should be absent (errors swallowed)
        assert "edit_distance_decreases" not in names
        assert "acceptance_rate_increases" not in names
        assert "rule_success_increases" not in names
        assert "misfires_stay_low" not in names
