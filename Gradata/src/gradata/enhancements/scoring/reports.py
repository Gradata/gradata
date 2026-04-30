"""
Report Generation — Brain health, metrics, and audit reports.
==============================================================
Engineering Spec Section 10 requires:
- Session CSV export
- Rolling metrics report
- Rule audit report
- Brain health report

All reports consume events from the events table (event-sourced).
"""

from __future__ import annotations
import logging

import csv
import io
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class HealthReport:
    """Brain health assessment."""

    brain_dir: str
    sessions_total: int
    events_total: int
    event_types: dict[str, int]  # type -> count
    corrections_total: int
    outputs_total: int
    correction_rate: float  # corrections / outputs
    first_draft_acceptance: float  # unedited outputs / total outputs
    rules_active: int
    lessons_active: int
    timestamp: str
    issues: list[str]  # health warnings

    @property
    def healthy(self) -> bool:
        return len(self.issues) == 0


def generate_health_report(db_path: Path) -> HealthReport:
    """Generate a brain health report from event data."""
    from pathlib import Path as _Path

    issues: list[str] = []
    db = _Path(db_path)

    if not db.exists():
        return HealthReport(
            brain_dir=str(db.parent),
            sessions_total=0,
            events_total=0,
            event_types={},
            corrections_total=0,
            outputs_total=0,
            correction_rate=0.0,
            first_draft_acceptance=0.0,
            rules_active=0,
            lessons_active=0,
            timestamp=datetime.now().isoformat(),
            issues=["system.db not found"],
        )

    conn = sqlite3.connect(str(db))
    try:
        # Total events
        try:
            total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        except sqlite3.OperationalError:
            total = 0
            issues.append("events table missing")

        # Event type distribution
        type_dist: dict[str, int] = {}
        try:
            rows = conn.execute(
                "SELECT type, COUNT(*) FROM events GROUP BY type ORDER BY COUNT(*) DESC"
            ).fetchall()
            type_dist = {r[0]: r[1] for r in rows}
        except sqlite3.OperationalError:
            logger.warning('Suppressed exception in generate_health_report', exc_info=True)

        # Sessions
        try:
            sessions = conn.execute("SELECT COUNT(DISTINCT session) FROM events").fetchone()[0]
        except sqlite3.OperationalError:
            sessions = 0

        corrections = type_dist.get("CORRECTION", 0)
        outputs = type_dist.get("OUTPUT", 0)

        # First-draft acceptance (domain-agnostic: checks major_edit flag, not user name)
        fda = 0.0
        if outputs > 0:
            try:
                # Count outputs where no CORRECTION followed with major_edit=true
                unedited = conn.execute(
                    "SELECT COUNT(*) FROM events WHERE type='OUTPUT' "
                    "AND data_json NOT LIKE '%\"major_edit\": true%'"
                ).fetchone()[0]
                fda = round(unedited / outputs, 4)
            except sqlite3.OperationalError:
                logger.warning('Suppressed exception in generate_health_report', exc_info=True)

        correction_rate = round(corrections / outputs, 4) if outputs > 0 else 0.0

        # Health checks
        if total == 0:
            issues.append("No events logged")
        if sessions < 3:
            issues.append(f"Only {sessions} sessions — need 3+ for meaningful metrics")
        if correction_rate > 0.5:
            issues.append(f"High correction rate: {correction_rate:.0%}")
        if "CALIBRATION" not in type_dist:
            issues.append("No CALIBRATION events — self-scoring not active")

        # Count lessons from working dir
        brain_dir = db.parent
        lessons_path = brain_dir.parent / ".claude" / "lessons.md"
        lessons_count = 0
        rules_count = 0
        if lessons_path.exists():
            text = lessons_path.read_text(encoding="utf-8")
            lessons_count = text.count("[INSTINCT") + text.count("[PATTERN")
            rules_count = text.count("[RULE")

    finally:
        conn.close()

    return HealthReport(
        brain_dir=str(db.parent),
        sessions_total=sessions,
        events_total=total,
        event_types=type_dist,
        corrections_total=corrections,
        outputs_total=outputs,
        correction_rate=correction_rate,
        first_draft_acceptance=fda,
        rules_active=rules_count,
        lessons_active=lessons_count,
        timestamp=datetime.now(UTC).isoformat(),
        issues=issues,
    )


def format_health_report(report: HealthReport) -> str:
    """Format health report as human-readable text."""
    status = "HEALTHY" if report.healthy else f"ISSUES ({len(report.issues)})"
    lines = [
        f"Brain Health Report — {status}",
        f"  Directory: {report.brain_dir}",
        f"  Sessions: {report.sessions_total} | Events: {report.events_total}",
        f"  Outputs: {report.outputs_total} | Corrections: {report.corrections_total}",
        f"  Correction rate: {report.correction_rate:.1%}",
        f"  First-draft acceptance: {report.first_draft_acceptance:.1%}",
        f"  Rules active: {report.rules_active} | Lessons active: {report.lessons_active}",
    ]
    if report.event_types:
        top_types = ", ".join(f"{k}:{v}" for k, v in list(report.event_types.items())[:5])
        lines.append(f"  Top events: {top_types}")
    if report.issues:
        lines.append("  Issues:")
        for issue in report.issues:
            lines.append(f"    - {issue}")
    return "\n".join(lines)


def export_session_csv(db_path: Path, output: io.StringIO | None = None) -> str:
    """Export per-session metrics as CSV.

    Columns: session, outputs, corrections, correction_rate, event_count
    """
    from pathlib import Path as _Path

    buf = output or io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["session", "outputs", "corrections", "correction_rate", "event_count"])

    db = _Path(db_path)
    if not db.exists():
        return buf.getvalue()

    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute("""
            SELECT session,
                   SUM(CASE WHEN type='OUTPUT' THEN 1 ELSE 0 END) as outputs,
                   SUM(CASE WHEN type='CORRECTION' THEN 1 ELSE 0 END) as corrections,
                   COUNT(*) as total
            FROM events
            WHERE session IS NOT NULL
            GROUP BY session
            ORDER BY session
        """).fetchall()

        for session, outputs, corrections, total in rows:
            rate = round(corrections / outputs, 4) if outputs > 0 else 0.0
            writer.writerow([session, outputs, corrections, rate, total])
    except sqlite3.OperationalError:
        logger.warning('Suppressed exception in export_session_csv', exc_info=True)
    finally:
        conn.close()

    return buf.getvalue()


def generate_metrics_report(db_path: Path, window: int = 20) -> str:
    """Generate rolling metrics report as formatted text."""
    from gradata.enhancements.metrics import compute_metrics, format_metrics

    m = compute_metrics(db_path, window)
    return format_metrics(m)


def generate_rule_audit(db_path: Path) -> str:
    """Audit all RULE_APPLICATION events for success/misfire rates."""
    from pathlib import Path as _Path

    db = _Path(db_path)
    if not db.exists():
        return "No database found."

    conn = sqlite3.connect(str(db))
    lines = ["Rule Application Audit", "=" * 40]

    try:
        rows = conn.execute("""
            SELECT data_json FROM events
            WHERE type = 'RULE_APPLICATION'
            ORDER BY id DESC
            LIMIT 500
        """).fetchall()

        if not rows:
            lines.append("No RULE_APPLICATION events found.")
            return "\n".join(lines)

        # Aggregate by rule_id
        rule_stats: dict[str, dict] = {}
        for (data_json,) in rows:
            data = json.loads(data_json) if data_json else {}
            rule_id = data.get("rule_id", "unknown")
            if rule_id not in rule_stats:
                rule_stats[rule_id] = {"total": 0, "accepted": 0, "misfired": 0, "contradicted": 0}
            rule_stats[rule_id]["total"] += 1
            if data.get("accepted"):
                rule_stats[rule_id]["accepted"] += 1
            if data.get("misfired"):
                rule_stats[rule_id]["misfired"] += 1
            if data.get("contradicted"):
                rule_stats[rule_id]["contradicted"] += 1

        lines.append(f"\n{len(rule_stats)} rules tracked, {len(rows)} total applications\n")
        for rule_id, stats in sorted(rule_stats.items(), key=lambda x: -x[1]["total"]):
            t = stats["total"]
            acc_rate = stats["accepted"] / t if t > 0 else 0
            mis_rate = stats["misfired"] / t if t > 0 else 0
            lines.append(f"  {rule_id}: {t} apps, {acc_rate:.0%} accepted, {mis_rate:.0%} misfired")
    except sqlite3.OperationalError:
        lines.append("events table not found.")
    finally:
        conn.close()

    return "\n".join(lines)
