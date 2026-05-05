"""
Coverage tests for src/gradata/enhancements/scoring/reports.py
Target: >=85% line coverage.

Strategy:
- Each public function exercised with: missing DB, empty DB, populated DB.
- Health checks (correction rate, sessions, calibration, events) exercised
  via parametrize over DB states.
- format_health_report covers both healthy and issues branches.
- export_session_csv covers: missing DB, no events table, single/multiple sessions.
- generate_rule_audit covers: missing DB, no rows, rows with accepted/misfired/contradicted.
- generate_metrics_report delegates to metrics module — light smoke-test only
  (that module has its own tests).
- No network, no real filesystem writes outside tmp_path.
"""

from __future__ import annotations

import csv
import io
import json
import sqlite3
from pathlib import Path

import pytest

from gradata.enhancements.scoring.reports import (
    HealthReport,
    export_session_csv,
    format_health_report,
    generate_health_report,
    generate_rule_audit,
)

# ---------------------------------------------------------------------------
# Helpers to build minimal SQLite DBs inside tmp_path
# ---------------------------------------------------------------------------


def _make_db(db_path: Path) -> sqlite3.Connection:
    """Create the events table and return an open connection."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE events (id INTEGER PRIMARY KEY, type TEXT, session INTEGER, data_json TEXT)"
    )
    conn.commit()
    return conn


def _insert(conn: sqlite3.Connection, type_: str, session: int, data: dict | None = None) -> None:
    data_json = json.dumps(data or {})
    conn.execute(
        "INSERT INTO events (type, session, data_json) VALUES (?, ?, ?)",
        (type_, session, data_json),
    )
    conn.commit()


# ===========================================================================
# HealthReport dataclass
# ===========================================================================


class TestHealthReportDataclass:
    def test_healthy_when_no_issues(self):
        r = HealthReport(
            brain_dir="/tmp/b",
            sessions_total=5,
            events_total=50,
            event_types={"OUTPUT": 40, "CORRECTION": 10},
            corrections_total=10,
            outputs_total=40,
            correction_rate=0.25,
            first_draft_acceptance=0.75,
            rules_active=3,
            lessons_active=7,
            timestamp="2026-01-01T00:00:00",
            issues=[],
        )
        assert r.healthy is True

    def test_not_healthy_when_issues_present(self):
        r = HealthReport(
            brain_dir="/tmp/b",
            sessions_total=0,
            events_total=0,
            event_types={},
            corrections_total=0,
            outputs_total=0,
            correction_rate=0.0,
            first_draft_acceptance=0.0,
            rules_active=0,
            lessons_active=0,
            timestamp="2026-01-01T00:00:00",
            issues=["system.db not found"],
        )
        assert r.healthy is False


# ===========================================================================
# generate_health_report — missing DB
# ===========================================================================


class TestGenerateHealthReportMissingDb:
    def test_returns_report_when_db_absent(self, tmp_path):
        db_path = tmp_path / "nonexistent.db"
        report = generate_health_report(db_path)
        assert isinstance(report, HealthReport)
        assert report.sessions_total == 0
        assert report.events_total == 0
        assert report.healthy is False
        assert any("not found" in i for i in report.issues)

    def test_brain_dir_matches_parent(self, tmp_path):
        db_path = tmp_path / "brain" / "system.db"
        report = generate_health_report(db_path)
        assert report.brain_dir == str(tmp_path / "brain")


# ===========================================================================
# generate_health_report — empty events table (no events)
# ===========================================================================


class TestGenerateHealthReportEmptyDb:
    @pytest.fixture
    def empty_db(self, tmp_path) -> Path:
        db_path = tmp_path / "system.db"
        conn = _make_db(db_path)
        conn.close()
        return db_path

    def test_no_events_issue_raised(self, empty_db):
        report = generate_health_report(empty_db)
        assert report.events_total == 0
        assert any("No events" in i for i in report.issues)

    def test_low_sessions_issue_raised(self, empty_db):
        report = generate_health_report(empty_db)
        # 0 sessions < 3 — should warn
        assert any("sessions" in i.lower() for i in report.issues)

    def test_calibration_missing_issue_raised(self, empty_db):
        report = generate_health_report(empty_db)
        assert any("CALIBRATION" in i for i in report.issues)

    def test_correction_rate_is_zero_for_no_outputs(self, empty_db):
        report = generate_health_report(empty_db)
        assert report.correction_rate == 0.0

    def test_first_draft_acceptance_zero_for_no_outputs(self, empty_db):
        report = generate_health_report(empty_db)
        assert report.first_draft_acceptance == 0.0


# ===========================================================================
# generate_health_report — populated DB
# ===========================================================================


class TestGenerateHealthReportPopulated:
    @pytest.fixture
    def rich_db(self, tmp_path) -> Path:
        """DB with 3 distinct sessions, OUTPUT/CORRECTION/CALIBRATION events."""
        db_path = tmp_path / "system.db"
        conn = _make_db(db_path)
        for s in [1, 2, 3, 4]:
            _insert(conn, "OUTPUT", s, {})
            _insert(conn, "OUTPUT", s, {})
            _insert(conn, "CORRECTION", s, {})
        _insert(conn, "CALIBRATION", 1, {})
        conn.close()
        return db_path

    def test_event_counts(self, rich_db):
        report = generate_health_report(rich_db)
        assert report.events_total > 0
        assert report.outputs_total == 8
        assert report.corrections_total == 4

    def test_sessions_counted(self, rich_db):
        report = generate_health_report(rich_db)
        assert report.sessions_total == 4

    def test_correction_rate_computed(self, rich_db):
        report = generate_health_report(rich_db)
        assert report.correction_rate == round(4 / 8, 4)

    def test_no_calibration_issue_absent(self, rich_db):
        report = generate_health_report(rich_db)
        assert not any("CALIBRATION" in i for i in report.issues)

    def test_event_types_populated(self, rich_db):
        report = generate_health_report(rich_db)
        assert "OUTPUT" in report.event_types
        assert "CORRECTION" in report.event_types
        assert "CALIBRATION" in report.event_types

    def test_timestamp_present(self, rich_db):
        report = generate_health_report(rich_db)
        assert report.timestamp  # non-empty

    def test_healthy_with_enough_data(self, rich_db):
        # 4 sessions (>=3), calibration present, correction rate 0.5 (not >0.5)
        report = generate_health_report(rich_db)
        # correction_rate == 0.5 exactly — not > 0.5, so no "High correction" issue
        # But events_total > 0 and sessions >= 3 and calibration present
        assert "High correction rate" not in " ".join(report.issues)


class TestGenerateHealthReportHighCorrectionRate:
    """Trigger the >0.5 correction rate health check."""

    def test_high_correction_rate_issue(self, tmp_path):
        db_path = tmp_path / "system.db"
        conn = _make_db(db_path)
        # 1 output, 2 corrections → rate > 0.5 impossible (corrections/outputs)
        # Use 3 corrections to 1 output → rate = 3.0 > 0.5
        _insert(conn, "OUTPUT", 1, {})
        _insert(conn, "CORRECTION", 1, {})
        _insert(conn, "CORRECTION", 1, {})
        _insert(conn, "CORRECTION", 1, {})
        _insert(conn, "CALIBRATION", 1, {})
        for s in [1, 2, 3]:
            _insert(conn, "OUTPUT", s, {})
        conn.close()
        report = generate_health_report(db_path)
        assert any("High correction rate" in i for i in report.issues)


class TestGenerateHealthReportMissingEventsTable:
    """DB file exists but has no events table — exercises OperationalError paths."""

    @pytest.fixture
    def bare_db(self, tmp_path) -> Path:
        db_path = tmp_path / "system.db"
        conn = sqlite3.connect(str(db_path))
        conn.close()
        return db_path

    def test_returns_report_without_crashing(self, bare_db):
        report = generate_health_report(bare_db)
        assert isinstance(report, HealthReport)

    def test_events_table_missing_issue(self, bare_db):
        report = generate_health_report(bare_db)
        assert any("missing" in i.lower() for i in report.issues)


# ===========================================================================
# generate_health_report — lessons.md parsing
# ===========================================================================


class TestHealthReportLessonsFile:
    def test_counts_instinct_and_pattern_and_rule(self, tmp_path):
        db_path = tmp_path / "system.db"
        conn = _make_db(db_path)
        conn.close()

        # Simulate the expected lessons.md location relative to db.parent
        # db.parent = tmp_path; lessons is db.parent.parent / ".claude" / "lessons.md"
        # So we need tmp_path.parent / ".claude" / lessons.md
        lessons_dir = tmp_path.parent / ".claude"
        lessons_dir.mkdir(exist_ok=True)
        lessons_file = lessons_dir / "lessons.md"
        lessons_file.write_text(
            "[INSTINCT] use active voice\n"
            "[INSTINCT] prefer short sentences\n"
            "[PATTERN] avoid passive\n"
            "[RULE] never start with 'I'\n",
            encoding="utf-8",
        )

        report = generate_health_report(db_path)
        # INSTINCT + PATTERN counts → lessons_active == 3
        assert report.lessons_active == 3
        assert report.rules_active == 1


# ===========================================================================
# format_health_report
# ===========================================================================


class TestFormatHealthReport:
    def _make_report(self, issues=None, event_types=None):
        return HealthReport(
            brain_dir="/brain",
            sessions_total=5,
            events_total=100,
            event_types=event_types or {},
            corrections_total=20,
            outputs_total=80,
            correction_rate=0.25,
            first_draft_acceptance=0.75,
            rules_active=4,
            lessons_active=10,
            timestamp="2026-01-01T00:00:00",
            issues=issues or [],
        )

    def test_healthy_status_label(self):
        text = format_health_report(self._make_report(issues=[]))
        assert "HEALTHY" in text

    def test_issues_status_label(self):
        text = format_health_report(self._make_report(issues=["problem A", "problem B"]))
        assert "ISSUES (2)" in text

    def test_issues_listed_individually(self):
        text = format_health_report(self._make_report(issues=["problem A", "problem B"]))
        assert "- problem A" in text
        assert "- problem B" in text

    def test_correction_rate_formatted(self):
        text = format_health_report(self._make_report())
        assert "25.0%" in text

    def test_first_draft_acceptance_formatted(self):
        text = format_health_report(self._make_report())
        assert "75.0%" in text

    def test_event_types_shown_when_present(self):
        text = format_health_report(self._make_report(event_types={"OUTPUT": 80, "CORRECTION": 20}))
        assert "Top events:" in text
        assert "OUTPUT:80" in text

    def test_no_event_types_section_when_empty(self):
        text = format_health_report(self._make_report(event_types={}))
        assert "Top events:" not in text

    def test_top_events_capped_at_five(self):
        many = {f"TYPE_{i}": i for i in range(10)}
        text = format_health_report(self._make_report(event_types=many))
        # Should only include first 5 items
        type_lines = [l for l in text.splitlines() if "Top events:" in l]
        assert len(type_lines) == 1
        # Count how many TYPE_ entries appear
        count = text.count("TYPE_")
        assert count <= 5

    def test_contains_directory(self):
        text = format_health_report(self._make_report())
        assert "/brain" in text

    def test_contains_sessions_and_events(self):
        text = format_health_report(self._make_report())
        assert "Sessions: 5" in text
        assert "Events: 100" in text


# ===========================================================================
# export_session_csv
# ===========================================================================


class TestExportSessionCsv:
    def test_missing_db_returns_header_only(self, tmp_path):
        db_path = tmp_path / "nope.db"
        result = export_session_csv(db_path)
        lines = result.strip().splitlines()
        assert len(lines) == 1
        assert lines[0] == "session,outputs,corrections,correction_rate,event_count"

    def test_no_events_table_returns_header_only(self, tmp_path):
        db_path = tmp_path / "system.db"
        conn = sqlite3.connect(str(db_path))
        conn.close()
        result = export_session_csv(db_path)
        lines = result.strip().splitlines()
        assert len(lines) == 1

    def test_single_session_csv_row(self, tmp_path):
        db_path = tmp_path / "system.db"
        conn = _make_db(db_path)
        _insert(conn, "OUTPUT", 1, {})
        _insert(conn, "OUTPUT", 1, {})
        _insert(conn, "CORRECTION", 1, {})
        conn.close()

        result = export_session_csv(db_path)
        reader = csv.DictReader(io.StringIO(result))
        rows = list(reader)
        assert len(rows) == 1
        row = rows[0]
        assert row["session"] == "1"
        assert row["outputs"] == "2"
        assert row["corrections"] == "1"
        assert float(row["correction_rate"]) == pytest.approx(0.5, abs=1e-4)
        assert row["event_count"] == "3"

    def test_multiple_sessions_ordered(self, tmp_path):
        db_path = tmp_path / "system.db"
        conn = _make_db(db_path)
        for s in [3, 1, 2]:
            _insert(conn, "OUTPUT", s, {})
        conn.close()

        result = export_session_csv(db_path)
        reader = csv.DictReader(io.StringIO(result))
        sessions = [int(r["session"]) for r in reader]
        assert sessions == sorted(sessions)

    def test_zero_outputs_correction_rate_zero(self, tmp_path):
        db_path = tmp_path / "system.db"
        conn = _make_db(db_path)
        _insert(conn, "CALIBRATION", 1, {})
        conn.close()

        result = export_session_csv(db_path)
        reader = csv.DictReader(io.StringIO(result))
        rows = list(reader)
        # CALIBRATION with session IS NOT NULL should appear as its own row
        assert len(rows) == 1
        assert float(rows[0]["correction_rate"]) == 0.0

    def test_accepts_output_buffer(self, tmp_path):
        db_path = tmp_path / "nope.db"
        buf = io.StringIO()
        result = export_session_csv(db_path, output=buf)
        assert "session" in result
        # The returned value is the buffer content
        assert result == buf.getvalue()

    @pytest.mark.parametrize("n_sessions", [1, 3, 5])
    def test_row_count_matches_sessions(self, tmp_path, n_sessions):
        db_path = tmp_path / f"system_{n_sessions}.db"
        conn = _make_db(db_path)
        for s in range(1, n_sessions + 1):
            _insert(conn, "OUTPUT", s, {})
        conn.close()

        result = export_session_csv(db_path)
        reader = csv.DictReader(io.StringIO(result))
        assert len(list(reader)) == n_sessions


# ===========================================================================
# generate_rule_audit
# ===========================================================================


class TestGenerateRuleAudit:
    def test_missing_db_returns_no_database_message(self, tmp_path):
        db_path = tmp_path / "missing.db"
        result = generate_rule_audit(db_path)
        assert "No database found." in result

    def test_no_events_table_returns_not_found_message(self, tmp_path):
        db_path = tmp_path / "system.db"
        conn = sqlite3.connect(str(db_path))
        conn.close()
        result = generate_rule_audit(db_path)
        assert "not found" in result.lower()

    def test_no_rule_application_events(self, tmp_path):
        db_path = tmp_path / "system.db"
        conn = _make_db(db_path)
        _insert(conn, "OUTPUT", 1, {})
        conn.close()
        result = generate_rule_audit(db_path)
        assert "No RULE_APPLICATION events found." in result

    def test_single_rule_accepted(self, tmp_path):
        db_path = tmp_path / "system.db"
        conn = _make_db(db_path)
        _insert(conn, "RULE_APPLICATION", 1, {"rule_id": "r1", "accepted": True})
        conn.close()
        result = generate_rule_audit(db_path)
        assert "r1" in result
        assert "100% accepted" in result

    def test_single_rule_misfired(self, tmp_path):
        db_path = tmp_path / "system.db"
        conn = _make_db(db_path)
        _insert(conn, "RULE_APPLICATION", 1, {"rule_id": "r2", "misfired": True})
        conn.close()
        result = generate_rule_audit(db_path)
        assert "r2" in result
        assert "100% misfired" in result

    def test_contradicted_flag_counted(self, tmp_path):
        db_path = tmp_path / "system.db"
        conn = _make_db(db_path)
        _insert(conn, "RULE_APPLICATION", 1, {"rule_id": "r3", "contradicted": True})
        conn.close()
        result = generate_rule_audit(db_path)
        assert "r3" in result

    def test_multiple_rules_sorted_by_total_desc(self, tmp_path):
        db_path = tmp_path / "system.db"
        conn = _make_db(db_path)
        # r_rare: 1 application, r_common: 3 applications
        _insert(conn, "RULE_APPLICATION", 1, {"rule_id": "r_rare", "accepted": True})
        for _ in range(3):
            _insert(conn, "RULE_APPLICATION", 1, {"rule_id": "r_common", "accepted": True})
        conn.close()
        result = generate_rule_audit(db_path)
        idx_common = result.index("r_common")
        idx_rare = result.index("r_rare")
        assert idx_common < idx_rare  # higher total appears first

    def test_rule_summary_header(self, tmp_path):
        db_path = tmp_path / "system.db"
        conn = _make_db(db_path)
        _insert(conn, "RULE_APPLICATION", 1, {"rule_id": "r1", "accepted": True})
        conn.close()
        result = generate_rule_audit(db_path)
        assert "Rule Application Audit" in result
        assert "rules tracked" in result

    def test_null_data_json_handled(self, tmp_path):
        """Row with NULL data_json should not crash — falls back to unknown rule."""
        db_path = tmp_path / "system.db"
        conn = _make_db(db_path)
        conn.execute(
            "INSERT INTO events (type, session, data_json) VALUES (?, ?, ?)",
            ("RULE_APPLICATION", 1, None),
        )
        conn.commit()
        conn.close()
        result = generate_rule_audit(db_path)
        assert "unknown" in result

    @pytest.mark.parametrize("n_rules", [1, 5, 10])
    def test_rule_count_in_summary(self, tmp_path, n_rules):
        db_path = tmp_path / f"system_{n_rules}.db"
        conn = _make_db(db_path)
        for i in range(n_rules):
            _insert(conn, "RULE_APPLICATION", 1, {"rule_id": f"rule_{i}"})
        conn.close()
        result = generate_rule_audit(db_path)
        assert f"{n_rules} rules tracked" in result


# ===========================================================================
# generate_metrics_report — smoke test (delegates to metrics module)
# ===========================================================================


class TestFirstDraftAcceptanceOperationalError:
    """Hit the except OperationalError branch inside the FDA block (lines 107-108).

    The branch fires when the FDA SELECT raises OperationalError despite the
    earlier queries succeeding.  sqlite3.Connection.execute is a read-only C
    slot in Python 3.12, so we use a subclass wrapper instead of monkeypatching
    the method directly.
    """

    def test_fda_operational_error_falls_back_to_zero(self, tmp_path, monkeypatch):
        db_path = tmp_path / "system.db"
        conn_real = _make_db(db_path)
        for s in [1, 2, 3]:
            _insert(conn_real, "OUTPUT", s, {})
        _insert(conn_real, "CALIBRATION", 1, {})
        conn_real.close()

        class _FaultyConn:
            """Thin wrapper that raises OperationalError on the FDA query."""

            def __init__(self, inner):
                self._inner = inner

            def execute(self, sql, *args, **kwargs):
                if "major_edit" in sql:
                    raise sqlite3.OperationalError("forced error")
                return self._inner.execute(sql, *args, **kwargs)

            def close(self):
                self._inner.close()

        original_connect = sqlite3.connect

        def patched_connect(path, *args, **kwargs):
            return _FaultyConn(original_connect(path, *args, **kwargs))

        monkeypatch.setattr(
            "gradata.enhancements.scoring.reports.sqlite3.connect",
            patched_connect,
        )

        report = generate_health_report(db_path)
        # fda stays at 0.0 when the OperationalError fires
        assert report.first_draft_acceptance == 0.0


class TestGenerateMetricsReport:
    def test_missing_db_returns_string(self, tmp_path):
        from gradata.enhancements.scoring.reports import generate_metrics_report

        db_path = tmp_path / "nope.db"
        result = generate_metrics_report(db_path)
        assert isinstance(result, str)

    def test_empty_db_returns_string(self, tmp_path):
        from gradata.enhancements.scoring.reports import generate_metrics_report

        db_path = tmp_path / "system.db"
        conn = _make_db(db_path)
        conn.close()
        result = generate_metrics_report(db_path)
        assert isinstance(result, str)

    def test_custom_window_accepted(self, tmp_path):
        from gradata.enhancements.scoring.reports import generate_metrics_report

        db_path = tmp_path / "nope.db"
        result = generate_metrics_report(db_path, window=5)
        assert isinstance(result, str)
