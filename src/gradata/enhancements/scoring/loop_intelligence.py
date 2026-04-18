"""
Loop Intelligence — Activity tracking, pattern aggregation, and prep-to-outcome analysis.
=========================================================================================

Extracted from brain/scripts/delta_tag.py and brain/scripts/patterns_updater.py (Wave 3).

Two subsystems:
1. **Activity Tracker** — Logs AI-assisted and manual activities, tracks prep-to-outcome links.
2. **Pattern Aggregator** — Reads tagged events, aggregates by dimension, updates markdown tables.

Both are domain-agnostic: activity types and prep types are configurable via registries.
Sales defaults are provided but any domain can register its own types.

Layer: enhancements/ (Layer 1) — imports from patterns/ only.
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from ..._events import emit as _emit_event_fn

# ═══════════════════════════════════════════════════════════════════
# Registries (domain-agnostic defaults, override via register_*)
# ═══════════════════════════════════════════════════════════════════

_ACTIVITY_TYPES: set[str] = {
    "email_sent", "email_received", "call", "meeting", "deal_stage_change",
}
_SOURCES: set[str] = {"claude_assisted", "manual", "instantly"}
_PREP_TYPES: set[str] = {"research", "personalization", "cheat_sheet", "email_draft"}
_OUTCOMES: set[str] = {"reply", "no_reply", "meeting_booked", "deal_advanced", "closed"}
_POSITIVE_OUTCOMES: set[str] = {
    "reply", "positive-reply", "meeting-booked", "demo-completed",
    "deal-advanced", "meeting_booked", "deal_advanced", "closed",
}


def register_activity_types(*types: str) -> None:
    """Register additional valid activity types."""
    _ACTIVITY_TYPES.update(types)


def register_prep_types(*types: str) -> None:
    """Register additional valid prep types."""
    _PREP_TYPES.update(types)


def register_outcomes(*outcomes: str, positive: bool = False) -> None:
    """Register additional valid outcomes. If positive=True, also marks them as positive."""
    _OUTCOMES.update(outcomes)
    if positive:
        _POSITIVE_OUTCOMES.update(outcomes)


# ═══════════════════════════════════════════════════════════════════
# Confidence bands
# ═══════════════════════════════════════════════════════════════════

def confidence_label(n: int) -> str:
    """Map sample count to a confidence label."""
    if n < 3:
        return "[INSUFFICIENT]"
    if n < 10:
        return "[HYPOTHESIS]"
    if n < 25:
        return "[EMERGING]"
    if n < 50:
        return "[PROVEN]"
    if n < 100:
        return "[HIGH CONFIDENCE]"
    return "[DEFINITIVE]"


# ═══════════════════════════════════════════════════════════════════
# Activity Tracker (from delta_tag.py)
# ═══════════════════════════════════════════════════════════════════

def _get_db(db_path: str | Path) -> sqlite3.Connection:
    """Get a connection with WAL mode and Row factory."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_tables(conn: sqlite3.Connection) -> None:
    """Ensure activity tracking tables exist. Safe to call repeatedly."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            date         TEXT NOT NULL,
            type         TEXT NOT NULL,
            prospect     TEXT,
            company      TEXT,
            detail       TEXT,
            source       TEXT DEFAULT 'claude_assisted',
            prep_level   INTEGER DEFAULT 0,
            session      INTEGER,
            timestamp    TEXT
        );
        CREATE TABLE IF NOT EXISTS prep_outcomes (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            date            TEXT NOT NULL,
            prospect        TEXT NOT NULL,
            prep_type       TEXT NOT NULL,
            prep_level      INTEGER DEFAULT 0,
            outcome         TEXT,
            days_to_outcome INTEGER,
            claude_assisted INTEGER DEFAULT 1,
            session         INTEGER,
            timestamp       TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_activity_log_date ON activity_log(date);
        CREATE INDEX IF NOT EXISTS idx_activity_log_source ON activity_log(source);
        CREATE INDEX IF NOT EXISTS idx_activity_log_prospect ON activity_log(prospect);
        CREATE INDEX IF NOT EXISTS idx_prep_outcomes_prospect ON prep_outcomes(prospect);
        CREATE INDEX IF NOT EXISTS idx_prep_outcomes_outcome ON prep_outcomes(outcome);
    """)
    # Migration: add columns if missing from older schema
    for table in ("activity_log", "prep_outcomes"):
        for col in ("session", "timestamp"):
            with contextlib.suppress(sqlite3.OperationalError):
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT DEFAULT NULL")


def log_activity(
    db_path: str | Path,
    activity_type: str,
    prospect: str = "",
    company: str = "",
    detail: str = "",
    prep_level: int = 0,
    source: str = "claude_assisted",
    session: int | None = None,
    date: str | None = None,
    emit_event: bool = True,
) -> dict[str, Any]:
    """Log an activity (email, call, meeting, deal change)."""
    today = date or datetime.now(UTC).strftime("%Y-%m-%d")
    now = datetime.now(UTC).isoformat()

    conn = _get_db(db_path)
    _init_tables(conn)

    cursor = conn.execute(
        """INSERT INTO activity_log
           (date, type, prospect, company, detail, source, prep_level, session, timestamp)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (today, activity_type, prospect, company, detail, source, prep_level, session, now),
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()

    if emit_event:
        # Never break the logging path on emit failure
        with contextlib.suppress(Exception):
            _emit_event_fn(
                "DELTA_TAG", "loop_intelligence",
                {
                    "activity_type": activity_type,
                    "prospect": prospect,
                    "company": company,
                    "source": source,
                    "prep_level": prep_level,
                    "detail": detail,
                    "activity_log_id": row_id,
                },
                tags=[t for t in [
                    f"prospect:{prospect}" if prospect else None,
                    f"type:{activity_type}",
                ] if t],
                session=session,
            )

    return {
        "id": row_id,
        "logged": f"{activity_type} | {prospect} | {source} | prep:{prep_level}",
    }


def log_prep(
    db_path: str | Path,
    prospect: str,
    prep_type: str,
    prep_level: int = 0,
    session: int | None = None,
    date: str | None = None,
) -> dict[str, Any]:
    """Log prep work for a prospect (before outcome is known)."""
    today = date or datetime.now(UTC).strftime("%Y-%m-%d")
    now = datetime.now(UTC).isoformat()

    conn = _get_db(db_path)
    _init_tables(conn)

    cursor = conn.execute(
        """INSERT INTO prep_outcomes
           (date, prospect, prep_type, prep_level, claude_assisted, session, timestamp)
           VALUES (?, ?, ?, ?, 1, ?, ?)""",
        (today, prospect, prep_type, prep_level, session, now),
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()

    return {
        "id": row_id,
        "logged": f"prep:{prep_type} | {prospect} | level:{prep_level}",
    }


def log_outcome(
    db_path: str | Path,
    prospect: str,
    prep_type: str,
    outcome: str,
    days: int = 0,
    date: str | None = None,
) -> dict[str, Any]:
    """Link an outcome to the most recent unresolved prep for this prospect+type."""
    today = date or datetime.now(UTC).strftime("%Y-%m-%d")

    conn = _get_db(db_path)
    _init_tables(conn)

    row = conn.execute(
        """SELECT id, date FROM prep_outcomes
           WHERE prospect = ? AND prep_type = ? AND outcome IS NULL
           ORDER BY date DESC, id DESC LIMIT 1""",
        (prospect, prep_type),
    ).fetchone()

    if row:
        if days == 0 and row["date"]:
            try:
                prep_date = datetime.strptime(row["date"], "%Y-%m-%d")
                outcome_date = datetime.strptime(today, "%Y-%m-%d")
                days = (outcome_date - prep_date).days
            except ValueError:
                pass

        conn.execute(
            "UPDATE prep_outcomes SET outcome = ?, days_to_outcome = ? WHERE id = ?",
            (outcome, days, row["id"]),
        )
        conn.commit()
        conn.close()
        return {
            "id": row["id"],
            "logged": f"outcome:{outcome} | {prospect} | {prep_type} | {days}d",
            "linked_to_prep": True,
        }
    else:
        cursor = conn.execute(
            """INSERT INTO prep_outcomes
               (date, prospect, prep_type, prep_level, outcome, days_to_outcome, claude_assisted, timestamp)
               VALUES (?, ?, ?, 0, ?, ?, 1, ?)""",
            (today, prospect, prep_type, outcome, days, datetime.now(UTC).isoformat()),
        )
        conn.commit()
        conn.close()
        return {
            "id": cursor.lastrowid,
            "logged": f"outcome:{outcome} | {prospect} | {prep_type} | {days}d",
            "linked_to_prep": False,
        }


def detect_manual(
    db_path: str | Path,
    gmail_sent: int = 0,
    crm_updates: int = 0,
    session_logged: int = 0,
    date: str | None = None,
) -> dict[str, Any]:
    """Detect manual activities by comparing external counts vs session-logged counts."""
    today = date or datetime.now(UTC).strftime("%Y-%m-%d")

    conn = _get_db(db_path)
    _init_tables(conn)

    ai_row = conn.execute(
        "SELECT COUNT(*) as c FROM activity_log WHERE date = ? AND source = 'claude_assisted'",
        (today,),
    ).fetchone()
    ai_count = ai_row["c"] if ai_row else 0

    manual_emails = max(0, gmail_sent - ai_count)
    manual_crm = max(0, crm_updates - session_logged)

    logged = []
    for i in range(manual_emails):
        log_activity(db_path, "email_sent",
                     detail=f"manual email #{i+1} (detected from external diff)",
                     source="manual", date=today, emit_event=False)
        logged.append("email_sent:manual")

    for i in range(manual_crm):
        log_activity(db_path, "deal_stage_change",
                     detail=f"manual CRM update #{i+1} (detected from external diff)",
                     source="manual", date=today, emit_event=False)
        logged.append("deal_stage_change:manual")

    conn.close()

    return {
        "ai_logged_today": ai_count,
        "manual_detected": manual_emails + manual_crm,
        "manual_emails": manual_emails,
        "manual_crm": manual_crm,
        "logged": logged,
    }


def get_activity_stats(db_path: str | Path, days: int = 30) -> dict[str, Any]:
    """Get activity and prep stats for the last N days."""
    conn = _get_db(db_path)
    _init_tables(conn)

    cutoff = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d")

    by_source = {
        r["source"]: r["c"]
        for r in conn.execute(
            "SELECT source, COUNT(*) as c FROM activity_log WHERE date >= ? GROUP BY source",
            (cutoff,),
        ).fetchall()
    }
    by_type = {
        r["type"]: r["c"]
        for r in conn.execute(
            "SELECT type, COUNT(*) as c FROM activity_log WHERE date >= ? GROUP BY type",
            (cutoff,),
        ).fetchall()
    }

    prep_stats = []
    for r in conn.execute(
        """SELECT prep_level, COUNT(*) as total,
                  SUM(CASE WHEN outcome IN ('reply','meeting_booked','deal_advanced','closed') THEN 1 ELSE 0 END) as positive,
                  AVG(days_to_outcome) as avg_days
           FROM prep_outcomes WHERE date >= ? GROUP BY prep_level""",
        (cutoff,),
    ).fetchall():
        rate = (r["positive"] / r["total"] * 100) if r["total"] > 0 else 0
        prep_stats.append({
            "level": r["prep_level"],
            "total": r["total"],
            "positive": r["positive"],
            "rate": round(rate, 1),
            "avg_days": round(r["avg_days"], 1) if r["avg_days"] else None,
        })

    total_activities = conn.execute(
        "SELECT COUNT(*) as c FROM activity_log WHERE date >= ?", (cutoff,),
    ).fetchone()["c"]
    total_outcomes = conn.execute(
        "SELECT COUNT(*) as c FROM prep_outcomes WHERE date >= ? AND outcome IS NOT NULL", (cutoff,),
    ).fetchone()["c"]
    pending_outcomes = conn.execute(
        "SELECT COUNT(*) as c FROM prep_outcomes WHERE date >= ? AND outcome IS NULL", (cutoff,),
    ).fetchone()["c"]

    conn.close()

    return {
        "period_days": days,
        "total_activities": total_activities,
        "by_source": by_source,
        "by_type": by_type,
        "total_outcomes_resolved": total_outcomes,
        "pending_outcomes": pending_outcomes,
        "prep_effectiveness": prep_stats,
    }


# ═══════════════════════════════════════════════════════════════════
# Pattern Aggregator (from patterns_updater.py)
# ═══════════════════════════════════════════════════════════════════

def query_tagged_interactions(
    db_path: str | Path,
    session: int | None = None,
    exclude_sources: tuple[str, ...] = ("instantly",),
) -> list[dict[str, str]]:
    """Query DELTA_TAG events with structured tags for pattern analysis."""
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        query = "SELECT data_json, tags_json FROM events WHERE type = 'DELTA_TAG'"
        params: list[Any] = []
        if session:
            query += " AND session = ?"
            params.append(session)

        rows = conn.execute(query, params).fetchall()
        conn.close()

        interactions = []
        for row in rows:
            data = json.loads(row["data_json"]) if row["data_json"] else {}
            tags = json.loads(row["tags_json"]) if row["tags_json"] else []

            tag_dict = {}
            for t in tags:
                if ":" in t:
                    k, v = t.split(":", 1)
                    tag_dict[k] = v

            if data.get("source") in exclude_sources:
                continue

            interactions.append({
                "prospect": tag_dict.get("prospect", data.get("prospect", "")),
                "angle": tag_dict.get("angle", data.get("angle", "")),
                "tone": tag_dict.get("tone", data.get("tone", "")),
                "persona": tag_dict.get("persona", data.get("persona", "")),
                "channel": tag_dict.get("channel", data.get("activity_type", "")),
                "outcome": tag_dict.get("outcome", data.get("outcome", "pending")),
                "framework": tag_dict.get("framework", data.get("framework", "")),
            })

        return interactions
    except Exception:
        return []


def aggregate_by_key(
    interactions: list[dict[str, str]],
    key: str,
    positive_outcomes: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Aggregate interactions by a key field. Returns {value: {sent, replies, rate, confidence}}."""
    pos = positive_outcomes or _POSITIVE_OUTCOMES
    stats: dict[str, dict[str, int]] = defaultdict(lambda: {"sent": 0, "replies": 0})

    for i in interactions:
        val = i.get(key, "")
        if not val:
            continue
        stats[val]["sent"] += 1
        if i.get("outcome") in pos:
            stats[val]["replies"] += 1

    result = {}
    for val, s in stats.items():
        rate = round(s["replies"] / s["sent"] * 100, 1) if s["sent"] > 0 else 0
        result[val] = {
            "sent": s["sent"],
            "replies": s["replies"],
            "rate": rate,
            "confidence": confidence_label(s["sent"]),
        }
    return result


def update_markdown_table(
    text: str,
    section_header: str,
    new_data: dict[str, dict[str, Any]],
    tier: str = "Pipeline",
) -> str:
    """Update tier-specific rows in a markdown table section. Adds new rows for new values."""
    if not new_data:
        return text

    data = dict(new_data)  # Copy so we can mutate
    lines = text.split("\n")
    in_section = False
    in_table = False
    header_line = -1
    last_table_line = -1

    for i, line in enumerate(lines):
        if line.strip().startswith(f"## {section_header}"):
            in_section = True
            continue
        if in_section and line.strip().startswith("## "):
            in_section = False
            continue
        if in_section and "|" in line and not in_table:
            header_line = i
            in_table = True
            continue
        if in_section and in_table and line.strip().startswith("|---"):
            continue
        if in_section and in_table and "|" in line:
            last_table_line = i
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if not cells:
                continue

            row_key = cells[0].strip().lower().replace(" ", "-")
            is_pipeline = tier in line or tier.lower() != "cold"

            if row_key in data and is_pipeline:
                d = data[row_key]
                has_tier = "Tier" in (lines[header_line] if header_line >= 0 else "")
                if has_tier:
                    lines[i] = f"| {cells[0]} | {d['sent']} | {d['replies']} | {d['rate']}% | {d['confidence']} | Pipeline | Auto-updated |"
                else:
                    lines[i] = f"| {cells[0]} | {d['sent']} | {d['replies']} | {d['rate']}% | {d['confidence']} |"
                del data[row_key]

        if in_section and in_table and not line.strip().startswith("|") and line.strip():
            in_table = False

    # Add new rows
    if data and last_table_line > 0:
        insert_at = last_table_line + 1
        has_tier = "Tier" in (lines[header_line] if header_line >= 0 else "")
        for val, d in data.items():
            display = val.replace("-", " ").title()
            if has_tier:
                new_row = f"| {display} | {d['sent']} | {d['replies']} | {d['rate']}% | {d['confidence']} | Pipeline | Auto-added |"
            else:
                new_row = f"| {display} | {d['sent']} | {d['replies']} | {d['rate']}% | {d['confidence']} |"
            lines.insert(insert_at, new_row)
            insert_at += 1

    return "\n".join(lines)


def update_patterns_file(
    db_path: str | Path,
    patterns_file: str | Path,
    session: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Main entry: update a patterns markdown file from tagged events."""
    pf = Path(patterns_file)
    if not pf.exists():
        return {"error": "patterns file not found", "path": str(pf)}

    interactions = query_tagged_interactions(db_path, session)
    if not interactions:
        return {"status": "no_data", "interactions": 0}

    by_angle = aggregate_by_key(interactions, "angle")
    by_tone = aggregate_by_key(interactions, "tone")
    by_persona = aggregate_by_key(interactions, "persona")
    by_framework = aggregate_by_key(interactions, "framework")

    text = pf.read_text(encoding="utf-8")
    original = text

    section_map = {
        "Reply Rates by Angle": by_angle,
        "Reply Rates by Tone": by_tone,
        "Reply Rates by Persona": by_persona,
        "Reply Rates by Framework": by_framework,
    }
    for header, data in section_map.items():
        if data:
            text = update_markdown_table(text, header, data)

    changed = text != original
    if changed and not dry_run:
        pf.write_text(text, encoding="utf-8")

    return {
        "status": "updated" if changed else "no_changes",
        "interactions": len(interactions),
        "by_angle": {k: v["sent"] for k, v in by_angle.items()},
        "by_tone": {k: v["sent"] for k, v in by_tone.items()},
        "by_persona": {k: v["sent"] for k, v in by_persona.items()},
        "by_framework": {k: v["sent"] for k, v in by_framework.items()},
        "dry_run": dry_run,
    }
