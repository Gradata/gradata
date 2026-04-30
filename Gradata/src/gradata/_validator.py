"""
Brain Validator — Independent Quality Verification for Marketplace Trust
========================================================================
SDK-native module. Validates a brain's claimed metrics against its event log.

Trust Dimensions:
    1. METRIC_INTEGRITY  — Do claimed numbers match the event log?
    2. TRAINING_DEPTH    — Is the brain actually trained, or padded?
    3. LEARNING_SIGNAL   — Does the brain learn (corrections decrease)?
    4. DATA_COMPLETENESS — Are events well-formed with required fields?
    5. BEHAVIORAL_COVERAGE — Do CARL rules cover declared capabilities?
"""

from __future__ import annotations
import logging

import json
import re
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import gradata._paths as _p
logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from gradata._paths import BrainContext

__all__ = [
    "main",
    "print_report",
    "save_validation",
    "validate_brain",
]


# ── Dimension 1: Metric Integrity ─────────────────────────────────────


def _verify_metrics(manifest: dict, conn: sqlite3.Connection) -> dict:
    """Compare claimed metrics against independently computed values."""
    results = []
    claimed = manifest.get("quality", {})
    db_meta = manifest.get("database", {})

    # 1a. Total events count
    try:
        actual_events = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    except Exception:
        actual_events = 0
    claimed_events = db_meta.get("total_events", 0)
    results.append(
        {
            "check": "total_events",
            "claimed": claimed_events,
            "actual": actual_events,
            "pass": actual_events >= claimed_events,
            "note": "actual >= claimed is valid (events accumulate)"
            if actual_events >= claimed_events
            else "claimed exceeds actual — inflation detected",
        }
    )

    # 1b. Event type count
    try:
        actual_types = conn.execute("SELECT COUNT(DISTINCT type) FROM events").fetchone()[0]
    except Exception:
        actual_types = 0
    claimed_types = db_meta.get("event_types", 0)
    results.append(
        {
            "check": "event_types",
            "claimed": claimed_types,
            "actual": actual_types,
            "pass": abs(actual_types - claimed_types) <= 2,
            "note": "within tolerance"
            if abs(actual_types - claimed_types) <= 2
            else "type count mismatch",
        }
    )

    # 1c. Lessons graduated count
    graduated_claimed = claimed.get("lessons_graduated", 0)
    graduated_actual = _count_lessons_in_file(_p.BRAIN_DIR / "lessons-archive.md")
    results.append(
        {
            "check": "lessons_graduated",
            "claimed": graduated_claimed,
            "actual": graduated_actual,
            "pass": abs(graduated_actual - graduated_claimed) <= 5,
            "note": "within tolerance"
            if abs(graduated_actual - graduated_claimed) <= 5
            else "graduated count mismatch",
        }
    )

    # 1d. Lessons active count
    active_claimed = claimed.get("lessons_active", 0)
    active_actual = _count_lessons_in_file(_p.LESSONS_FILE)
    results.append(
        {
            "check": "lessons_active",
            "claimed": active_claimed,
            "actual": active_actual,
            "pass": abs(active_actual - active_claimed) <= 3,
            "note": "within tolerance"
            if abs(active_actual - active_claimed) <= 3
            else "active count mismatch",
        }
    )

    # 1e. Session count
    sessions_claimed = manifest.get("metadata", {}).get("sessions_trained", 0)
    try:
        sessions_actual = (
            conn.execute(
                "SELECT MAX(session) FROM events WHERE typeof(session)='integer'"
            ).fetchone()[0]
            or 0
        )
    except Exception:
        sessions_actual = 0
    results.append(
        {
            "check": "sessions_trained",
            "claimed": sessions_claimed,
            "actual": sessions_actual,
            "pass": abs(sessions_actual - sessions_claimed) <= 3,
            "note": "within tolerance"
            if abs(sessions_actual - sessions_claimed) <= 3
            else "session count mismatch",
        }
    )

    # 1f. Table count
    claimed_tables = len(db_meta.get("tables", []))
    try:
        actual_tables = len(
            conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        )
    except Exception:
        actual_tables = 0
    results.append(
        {
            "check": "db_tables",
            "claimed": claimed_tables,
            "actual": actual_tables,
            "pass": actual_tables >= claimed_tables,
            "note": "ok" if actual_tables >= claimed_tables else "tables missing from DB",
        }
    )

    passed = sum(1 for r in results if r["pass"])
    return {
        "dimension": "METRIC_INTEGRITY",
        "score": round(passed / len(results), 3) if results else 0,
        "passed": passed,
        "total": len(results),
        "checks": results,
    }


# ── Dimension 2: Training Depth ───────────────────────────────────────


def _verify_training_depth(manifest: dict, conn: sqlite3.Connection) -> dict:
    """Is this brain genuinely trained or just padded with empty sessions?"""
    results = []

    # 2a. Events per session distribution (padding detection)
    try:
        rows = conn.execute("""
            SELECT session, COUNT(*) as cnt FROM events
            GROUP BY session ORDER BY session
        """).fetchall()
    except Exception:
        rows = []

    if rows:
        counts = [r[1] for r in rows]
        avg_events = sum(counts) / len(counts)
        empty_sessions = sum(1 for c in counts if c <= 1)
        total_sessions = len(counts)

        results.append(
            {
                "check": "avg_events_per_session",
                "value": round(avg_events, 1),
                "pass": avg_events >= 3,
                "note": f"{avg_events:.1f} events/session (minimum useful: 3)"
                if avg_events >= 3
                else "suspiciously low event density — padding?",
            }
        )
        results.append(
            {
                "check": "empty_session_ratio",
                "value": round(empty_sessions / total_sessions, 3) if total_sessions > 0 else 1.0,
                "pass": (empty_sessions / total_sessions < 0.3) if total_sessions > 0 else False,
                "note": f"{empty_sessions}/{total_sessions} sessions with <=1 event",
            }
        )

    # 2b. Event type diversity (real training produces varied events)
    try:
        type_counts = conn.execute("""
            SELECT type, COUNT(*) FROM events GROUP BY type
        """).fetchall()
    except Exception:
        type_counts = []

    if type_counts:
        types_used = len(type_counts)
        results.append(
            {
                "check": "event_type_diversity",
                "value": types_used,
                "pass": types_used >= 5,
                "note": f"{types_used} distinct event types (minimum for real training: 5)",
            }
        )

    # 2c. Temporal span (brain trained over real time, not one burst)
    try:
        span = conn.execute("""
            SELECT MIN(ts), MAX(ts) FROM events
        """).fetchone()
    except Exception:
        span = (None, None)

    if span and span[0] and span[1]:
        try:
            first = datetime.fromisoformat(str(span[0]))
            last = datetime.fromisoformat(str(span[1]))
            days = (last - first).days
            results.append(
                {
                    "check": "training_span_days",
                    "value": days,
                    "pass": days >= 3,
                    "note": f"Trained over {days} days"
                    if days >= 3
                    else "all training in <3 days — insufficient maturation",
                }
            )
        except Exception:
            logger.warning('Suppressed exception in _verify_training_depth', exc_info=True)

    # 2d. CORRECTION events exist (brain was actually corrected = real interaction)
    try:
        correction_count = conn.execute(
            "SELECT COUNT(*) FROM events WHERE type = 'CORRECTION'"
        ).fetchone()[0]
    except Exception:
        correction_count = 0

    results.append(
        {
            "check": "corrections_exist",
            "value": correction_count,
            "pass": correction_count >= 3,
            "note": f"{correction_count} corrections (minimum for credible training: 3)",
        }
    )

    passed = sum(1 for r in results if r["pass"])
    return {
        "dimension": "TRAINING_DEPTH",
        "score": round(passed / len(results), 3) if results else 0,
        "passed": passed,
        "total": len(results),
        "checks": results,
    }


# ── Dimension 3: Learning Signal ──────────────────────────────────────


def _verify_learning_signal(manifest: dict, conn: sqlite3.Connection) -> dict:
    """Does the brain actually learn? Corrections should decrease over time."""
    results = []

    # 3a. Correction trend (later sessions should have fewer corrections)
    try:
        rows = conn.execute("""
            SELECT session, COUNT(*) FROM events
            WHERE type = 'CORRECTION'
            GROUP BY session ORDER BY session
        """).fetchall()
    except Exception:
        rows = []

    if len(rows) >= 4:
        counts = [r[1] for r in rows]
        mid = len(counts) // 2
        first_half_avg = sum(counts[:mid]) / mid if mid > 0 else 0
        second_half_avg = sum(counts[mid:]) / (len(counts) - mid) if (len(counts) - mid) > 0 else 0

        improving = second_half_avg <= first_half_avg
        results.append(
            {
                "check": "correction_trend",
                "first_half_avg": round(first_half_avg, 2),
                "second_half_avg": round(second_half_avg, 2),
                "pass": improving,
                "note": f"Early avg: {first_half_avg:.1f}, Recent avg: {second_half_avg:.1f} — {'improving' if improving else 'NOT improving'}",
            }
        )
    else:
        results.append(
            {
                "check": "correction_trend",
                "pass": False,
                "note": f"Insufficient correction data ({len(rows)} sessions with corrections, need 4+)",
            }
        )

    # 3b. Lesson graduation rate (lessons should move from INSTINCT to PATTERN to RULE)
    lessons_file = _p.LESSONS_FILE
    archive_file = _p.BRAIN_DIR / "lessons-archive.md"
    active = _count_lessons_in_file(lessons_file)
    graduated = _count_lessons_in_file(archive_file)
    total = active + graduated

    if total > 0:
        grad_rate = graduated / total
        results.append(
            {
                "check": "graduation_rate",
                "value": round(grad_rate, 3),
                "active": active,
                "graduated": graduated,
                "pass": grad_rate >= 0.3,
                "note": f"{graduated}/{total} lessons graduated ({grad_rate:.0%})"
                if grad_rate >= 0.3
                else f"Low graduation rate ({grad_rate:.0%}) — brain retains but doesn't crystallize",
            }
        )
    else:
        results.append(
            {
                "check": "graduation_rate",
                "pass": False,
                "note": "No lessons found — brain has no learning pipeline",
            }
        )

    # 3c. Lesson application tracking (lessons are actually applied, not just stored)
    try:
        app_count = conn.execute("SELECT COUNT(*) FROM lesson_applications").fetchone()[0]
    except Exception:
        app_count = 0

    results.append(
        {
            "check": "lesson_applications",
            "value": app_count,
            "pass": app_count >= 1,
            "note": f"{app_count} lesson applications tracked"
            if app_count >= 1
            else "No lesson applications — lessons exist but aren't applied",
        }
    )

    passed = sum(1 for r in results if r["pass"])
    return {
        "dimension": "LEARNING_SIGNAL",
        "score": round(passed / len(results), 3) if results else 0,
        "passed": passed,
        "total": len(results),
        "checks": results,
    }


# ── Dimension 4: Data Completeness ────────────────────────────────────


def _verify_data_completeness(manifest: dict, conn: sqlite3.Connection) -> dict:
    """Are events well-formed with required fields?"""
    results = []

    # 4a. Events have timestamps
    try:
        total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        with_ts = conn.execute(
            "SELECT COUNT(*) FROM events WHERE ts IS NOT NULL AND ts != ''"
        ).fetchone()[0]
    except Exception:
        total, with_ts = 0, 0

    if total > 0:
        ts_rate = with_ts / total
        results.append(
            {
                "check": "timestamp_coverage",
                "value": round(ts_rate, 3),
                "pass": ts_rate >= 0.95,
                "note": f"{ts_rate:.0%} of events have timestamps",
            }
        )

    # 4b. Events have session numbers
    try:
        with_session = conn.execute(
            "SELECT COUNT(*) FROM events WHERE session IS NOT NULL"
        ).fetchone()[0]
    except Exception:
        with_session = 0

    if total > 0:
        session_rate = with_session / total
        results.append(
            {
                "check": "session_coverage",
                "value": round(session_rate, 3),
                "pass": session_rate >= 0.90,
                "note": f"{session_rate:.0%} of events have session numbers",
            }
        )

    # 4c. Events have data payloads
    try:
        with_data = conn.execute(
            "SELECT COUNT(*) FROM events WHERE data_json IS NOT NULL AND data_json != '{}'"
        ).fetchone()[0]
    except Exception:
        with_data = 0

    if total > 0:
        data_rate = with_data / total
        results.append(
            {
                "check": "data_coverage",
                "value": round(data_rate, 3),
                "pass": data_rate >= 0.80,
                "note": f"{data_rate:.0%} of events have data payloads",
            }
        )

    # 4d. CORRECTION events have category tags
    try:
        corrections_total = conn.execute(
            "SELECT COUNT(*) FROM events WHERE type = 'CORRECTION'"
        ).fetchone()[0]
        corrections_tagged = conn.execute("""
            SELECT COUNT(*) FROM events
            WHERE type = 'CORRECTION'
            AND (data_json LIKE '%category%' OR tags_json LIKE '%category%')
        """).fetchone()[0]
    except Exception:
        corrections_total, corrections_tagged = 0, 0

    if corrections_total > 0:
        tag_rate = corrections_tagged / corrections_total
        results.append(
            {
                "check": "correction_categorization",
                "value": round(tag_rate, 3),
                "pass": tag_rate >= 0.70,
                "note": f"{tag_rate:.0%} of corrections are categorized",
            }
        )

    # 4e. events.jsonl exists and is consistent with DB
    jsonl_count = 0
    if _p.EVENTS_JSONL.exists():
        try:
            with open(_p.EVENTS_JSONL, encoding="utf-8") as f:
                jsonl_count = sum(1 for line in f if line.strip())
        except Exception:
            logger.warning('Suppressed exception in _verify_data_completeness', exc_info=True)

    if total > 0:
        sync_ratio = jsonl_count / total if total > 0 else 0
        results.append(
            {
                "check": "dual_write_consistency",
                "db_count": total,
                "jsonl_count": jsonl_count,
                "pass": 0.8 <= sync_ratio <= 1.3,
                "note": f"DB: {total}, JSONL: {jsonl_count} — {'consistent' if 0.8 <= sync_ratio <= 1.3 else 'drift detected'}",
            }
        )

    passed = sum(1 for r in results if r["pass"])
    return {
        "dimension": "DATA_COMPLETENESS",
        "score": round(passed / len(results), 3) if results else 0,
        "passed": passed,
        "total": len(results),
        "checks": results,
    }


# ── Dimension 5: Behavioral Coverage ──────────────────────────────────


def _verify_behavioral_coverage(manifest: dict, conn: sqlite3.Connection) -> dict:
    """Do CARL rules cover the brain's declared capabilities?"""
    results = []
    contract = manifest.get("behavioral_contract", {})

    # 5a. Safety rules exist
    safety = contract.get("safety_rules", 0)
    results.append(
        {
            "check": "safety_rules",
            "value": safety,
            "pass": safety >= 3,
            "note": f"{safety} safety rules"
            if safety >= 3
            else "insufficient safety rules for marketplace distribution",
        }
    )

    # 5b. Global rules exist
    global_rules = contract.get("global_rules", 0)
    results.append(
        {
            "check": "global_rules",
            "value": global_rules,
            "pass": global_rules >= 2,
            "note": f"{global_rules} global rules",
        }
    )

    # 5c. Total rule coverage is proportional to training
    total_rules = contract.get("total", 0)
    sessions = manifest.get("metadata", {}).get("sessions_trained", 0)
    rule_density = total_rules / max(sessions, 1)
    results.append(
        {
            "check": "rule_density",
            "value": round(rule_density, 2),
            "total_rules": total_rules,
            "sessions": sessions,
            "pass": rule_density >= 0.5,
            "note": f"{total_rules} rules / {sessions} sessions = {rule_density:.1f} rules/session",
        }
    )

    # 5d. Tag taxonomy exists and has entries
    taxonomy = manifest.get("tag_taxonomy", {})
    tax_count = len(taxonomy)
    results.append(
        {
            "check": "tag_taxonomy",
            "value": tax_count,
            "pass": tax_count >= 3,
            "note": f"{tax_count} tag prefixes defined"
            if tax_count >= 3
            else "insufficient tag vocabulary",
        }
    )

    passed = sum(1 for r in results if r["pass"])
    return {
        "dimension": "BEHAVIORAL_COVERAGE",
        "score": round(passed / len(results), 3) if results else 0,
        "passed": passed,
        "total": len(results),
        "checks": results,
    }


# ── Helpers ───────────────────────────────────────────────────────────


def _count_lessons_in_file(filepath: Path) -> int:
    """Count lesson entries in a lessons file."""
    if not filepath.exists():
        return 0
    try:
        text = filepath.read_text(encoding="utf-8")
        return len(re.findall(r"^\[20\d{2}-\d{2}-\d{2}\]", text, re.MULTILINE))
    except Exception:
        return 0


def _compute_trust_score(dimensions: list[dict]) -> dict:
    """Compute overall trust score from dimension scores."""
    if not dimensions:
        return {"score": 0, "grade": "F", "verdict": "UNTRUSTED"}

    weights = {
        "METRIC_INTEGRITY": 0.30,
        "TRAINING_DEPTH": 0.20,
        "LEARNING_SIGNAL": 0.25,
        "DATA_COMPLETENESS": 0.15,
        "BEHAVIORAL_COVERAGE": 0.10,
    }

    weighted_sum = 0
    weight_total = 0
    for dim in dimensions:
        w = weights.get(dim["dimension"], 0.1)
        weighted_sum += dim["score"] * w
        weight_total += w

    score = round(weighted_sum / weight_total, 3) if weight_total > 0 else 0

    if score >= 0.90:
        grade, verdict = "A", "TRUSTED"
    elif score >= 0.75:
        grade, verdict = "B", "VERIFIED"
    elif score >= 0.60:
        grade, verdict = "C", "PROVISIONAL"
    elif score >= 0.40:
        grade, verdict = "D", "CAUTION"
    else:
        grade, verdict = "F", "UNTRUSTED"

    return {"score": score, "grade": grade, "verdict": verdict}


# ── Main Validation ──────────────────────────────────────────────────


def validate_brain(manifest_path: Path | None = None, ctx: BrainContext | None = None) -> dict:
    """Run full brain validation. Returns structured report."""
    brain_dir = ctx.brain_dir if ctx else _p.BRAIN_DIR
    path = manifest_path or (brain_dir / "brain.manifest.json")

    if not path.exists():
        return {
            "error": f"Manifest not found: {path}",
            "trust": {"score": 0, "grade": "F", "verdict": "UNTRUSTED"},
        }

    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {
            "error": f"Invalid manifest JSON: {e}",
            "trust": {"score": 0, "grade": "F", "verdict": "UNTRUSTED"},
        }

    # Connect to DB
    db_path = path.parent / "system.db"
    if not db_path.exists():
        db_path = ctx.db_path if ctx else _p.DB_PATH
    try:
        conn = sqlite3.connect(str(db_path))
    except Exception as e:
        return {
            "error": f"Cannot open DB: {e}",
            "trust": {"score": 0, "grade": "F", "verdict": "UNTRUSTED"},
        }

    dimensions = [
        _verify_metrics(manifest, conn),
        _verify_training_depth(manifest, conn),
        _verify_learning_signal(manifest, conn),
        _verify_data_completeness(manifest, conn),
        _verify_behavioral_coverage(manifest, conn),
    ]

    conn.close()

    trust = _compute_trust_score(dimensions)

    total_checks = sum(d["total"] for d in dimensions)
    total_passed = sum(d["passed"] for d in dimensions)

    report = {
        "schema_version": "1.0.0",
        "validated_at": datetime.now(UTC).isoformat(),
        "manifest_path": str(path),
        "brain_version": manifest.get("metadata", {}).get("brain_version", "unknown"),
        "domain": manifest.get("metadata", {}).get("domain", "unknown"),
        "trust": trust,
        "summary": {
            "total_checks": total_checks,
            "passed": total_passed,
            "failed": total_checks - total_passed,
            "pass_rate": round(total_passed / total_checks, 3) if total_checks > 0 else 0,
        },
        "dimensions": dimensions,
    }

    return report


def save_validation(report: dict, ctx: BrainContext | None = None):
    """Save validation report to brain/validations/."""
    brain_dir = ctx.brain_dir if ctx else _p.BRAIN_DIR
    validations_dir = brain_dir / "validations"
    validations_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    path = validations_dir / f"{date_str}.json"
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return path


def print_report(report: dict):
    """Print human-readable validation report."""
    trust = report.get("trust", {})
    summary = report.get("summary", {})

    print("=" * 60)
    print("BRAIN VALIDATION REPORT")
    print("=" * 60)
    print(f"Brain:    {report.get('brain_version', '?')} ({report.get('domain', '?')})")
    print(f"Date:     {report.get('validated_at', '?')[:19]}")
    print(
        f"Trust:    {trust.get('grade', '?')} ({trust.get('score', 0):.0%}) — {trust.get('verdict', '?')}"
    )
    print(
        f"Checks:   {summary.get('passed', 0)}/{summary.get('total_checks', 0)} passed ({summary.get('pass_rate', 0):.0%})"
    )
    print()

    for dim in report.get("dimensions", []):
        icon = "PASS" if dim["score"] >= 0.75 else ("WARN" if dim["score"] >= 0.50 else "FAIL")
        print(f"[{icon}] {dim['dimension']}: {dim['score']:.0%} ({dim['passed']}/{dim['total']})")
        for check in dim.get("checks", []):
            status = "+" if check.get("pass") else "-"
            note = check.get("note", "")
            print(f"    [{status}] {check.get('check', '?')}: {note}")
        print()

    print("=" * 60)
    print(
        f"VERDICT: {trust.get('verdict', 'UNKNOWN')} (Grade {trust.get('grade', '?')}, Score {trust.get('score', 0):.0%})"
    )
    print("=" * 60)


# ── CLI ──────────────────────────────────────────────────────────────


def main():
    """Standalone CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate brain quality independently")
    parser.add_argument("--manifest", type=str, help="Path to brain.manifest.json")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--strict", action="store_true", help="Exit code 1 on any failure")
    parser.add_argument("--save", action="store_true", help="Save report to brain/validations/")
    args = parser.parse_args()

    manifest_path = Path(args.manifest) if args.manifest else None
    report = validate_brain(manifest_path)

    if args.save:
        saved = save_validation(report)
        print(f"Saved: {saved}")

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print_report(report)

    if args.strict:
        trust = report.get("trust", {})
        if trust.get("grade", "F") in ("D", "F"):
            sys.exit(1)
