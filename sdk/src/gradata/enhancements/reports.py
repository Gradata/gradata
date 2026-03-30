"""
Reports — Health, CSV, metrics, and rule audit reports.
=======================================================
SDK LAYER: Layer 1 (enhancements). Pure Python.

Open-source version provides basic health reporting.
Full reporting (CSV export, rule audit) is cloud-side.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class HealthReport:
    """Brain health assessment."""
    healthy: bool = True
    issues: list[str] = field(default_factory=list)
    sessions_total: int = 0
    events_total: int = 0
    lessons_active: int = 0


def generate_health_report(db_path=None, ctx=None) -> HealthReport:
    """Generate a basic health report from the brain database."""
    report = HealthReport()
    try:
        import sqlite3
        db = Path(db_path) if db_path else (Path(ctx.brain_dir) / "system.db" if ctx else None)
        if db and db.exists():
            conn = sqlite3.connect(str(db))
            report.sessions_total = conn.execute(
                "SELECT COUNT(DISTINCT session) FROM events"
            ).fetchone()[0] or 0
            report.events_total = conn.execute(
                "SELECT COUNT(*) FROM events"
            ).fetchone()[0] or 0
            conn.close()
    except Exception:
        report.issues.append("Could not read database")
        report.healthy = False
    return report


def format_health_report(report: HealthReport) -> str:
    """Format health report as human-readable string."""
    status = "HEALTHY" if report.healthy else "UNHEALTHY"
    lines = [
        f"Brain Health: {status}",
        f"  Sessions: {report.sessions_total}",
        f"  Events: {report.events_total}",
        f"  Active lessons: {report.lessons_active}",
    ]
    if report.issues:
        lines.append("  Issues:")
        for issue in report.issues:
            lines.append(f"    - {issue}")
    return "\n".join(lines)


def export_session_csv(db_path=None, ctx=None) -> str:
    """Export session metrics as CSV string. Basic open-source version."""
    return ""


def generate_metrics_report(db_path=None, window: int = 20, ctx=None) -> str:
    """Generate metrics report. Basic open-source version."""
    return "Metrics report: use gradata cloud for detailed reports."


def generate_rule_audit(db_path=None, ctx=None) -> str:
    """Generate rule audit report. Basic open-source version."""
    return "Rule audit: use gradata cloud for detailed audits."
