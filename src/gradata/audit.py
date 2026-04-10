"""
Audit Trail + Provenance — SQLite-backed rule provenance tracking.
===================================================================
SDK LAYER: Layer 0 (no Brain dependency). All functions take primitive
paths so they can be used without instantiating a Brain object.
Brain gets a thin 1-line trace() wrapper.

Tracks which corrections led to which rules, enabling full lineage
from correction → lesson → graduated rule.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Write provenance
# ---------------------------------------------------------------------------

def write_provenance(
    db_path: str | Path,
    *,
    rule_id: str,
    correction_event_id: str | None,
    session: int | None,
    timestamp: str,
    user_context: str | None,
) -> None:
    """Insert a provenance row linking a rule to a correction event.

    Args:
        db_path: Path to system.db.
        rule_id: Stable rule ID (sha256 hash from inspection._make_rule_id).
        correction_event_id: Event ID from events.jsonl that created this rule.
        session: Session number when the graduation occurred.
        timestamp: ISO timestamp of the graduation.
        user_context: Optional context string (e.g. task type, working dir).
    """
    from gradata._db import get_connection

    try:
        with get_connection(db_path) as conn:
            conn.execute(
                "INSERT INTO rule_provenance "
                "(rule_id, correction_event_id, session, timestamp, user_context) "
                "VALUES (?, ?, ?, ?, ?)",
                (rule_id, correction_event_id, session, timestamp, user_context),
            )
    except Exception as e:
        _log.debug("write_provenance failed: %s", e)


# ---------------------------------------------------------------------------
# Query provenance
# ---------------------------------------------------------------------------

def query_provenance(
    db_path: str | Path,
    *,
    rule_id: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Query the rule_provenance table.

    Args:
        db_path: Path to system.db.
        rule_id: Filter by rule_id. If None, returns all rows.
        limit: Max rows to return (default 50).

    Returns:
        List of provenance dicts with keys: id, rule_id, correction_event_id,
        session, timestamp, user_context.
    """
    db = Path(db_path)
    if not db.is_file():
        return []

    try:
        with sqlite3.connect(str(db)) as conn:
            conn.row_factory = sqlite3.Row
            if rule_id is not None:
                rows = conn.execute(
                    "SELECT * FROM rule_provenance WHERE rule_id = ? ORDER BY id DESC LIMIT ?",
                    (rule_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM rule_provenance ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        _log.debug("query_provenance failed: %s", e)
        return []


# ---------------------------------------------------------------------------
# Scan events.jsonl for specific IDs
# ---------------------------------------------------------------------------

def _scan_events_for_ids(
    events_path: str | Path,
    event_ids: list[str],
) -> list[dict]:
    """Scan events.jsonl for events matching the given IDs.

    Args:
        events_path: Path to events.jsonl file.
        event_ids: List of event IDs to find.

    Returns:
        List of matching event dicts.
    """
    p = Path(events_path)
    if not p.is_file():
        return []

    target_ids = set(event_ids)
    found: list[dict] = []

    try:
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                    if evt.get("id") in target_ids:
                        found.append(evt)
                        # Early exit if all found
                        if len(found) == len(target_ids):
                            break
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        _log.debug("_scan_events_for_ids failed: %s", e)

    return found


# ---------------------------------------------------------------------------
# Full trace: provenance + events + transitions
# ---------------------------------------------------------------------------

def trace_rule(
    db_path: str | Path,
    events_path: str | Path,
    lessons_path: str | Path,
    rule_id: str,
) -> dict:
    """Full trace of a rule: provenance table, events fallback, transitions.

    Args:
        db_path: Path to system.db.
        events_path: Path to events.jsonl.
        lessons_path: Path to lessons.md.
        rule_id: Stable rule ID to trace.

    Returns:
        Dict with keys: rule_id, rule, provenance, corrections, transitions.
        Returns {"error": "..."} if rule_id not found in lessons.
    """
    from gradata.inspection import _lesson_to_dict, _load_lessons_from_path, _make_rule_id

    lessons = _load_lessons_from_path(lessons_path)

    # Find the lesson matching this rule_id
    target = None
    for lesson in lessons:
        if _make_rule_id(lesson) == rule_id:
            target = lesson
            break

    if target is None:
        return {"error": f"Rule not found: {rule_id}"}

    # Get provenance rows from SQLite
    provenance = query_provenance(db_path, rule_id=rule_id)

    # Get correction events — from provenance table first, fallback to lesson's IDs
    correction_event_ids: list[str] = []
    if provenance:
        correction_event_ids = [
            r["correction_event_id"] for r in provenance
            if r.get("correction_event_id")
        ]
    if not correction_event_ids and target.correction_event_ids:
        correction_event_ids = target.correction_event_ids

    # Scan events.jsonl for the actual correction events
    corrections: list[dict] = []
    if correction_event_ids:
        corrections = _scan_events_for_ids(events_path, correction_event_ids)

    # Get transitions from SQLite
    transitions: list[dict] = []
    db = Path(db_path)
    if db.is_file():
        try:
            with sqlite3.connect(str(db)) as conn:
                conn.row_factory = sqlite3.Row
                # Query by description[:100] to match how transitions are stored
                rows = conn.execute(
                    """SELECT old_state, new_state, confidence, fire_count,
                              session, transitioned_at
                       FROM lesson_transitions
                       WHERE lesson_desc = ? AND category = ?
                       ORDER BY transitioned_at""",
                    (target.description[:100], target.category),
                ).fetchall()
                transitions = [dict(r) for r in rows]
        except Exception as e:
            _log.debug("Failed to query lesson_transitions: %s", e)

    return {
        "rule_id": rule_id,
        "rule": _lesson_to_dict(target),
        "provenance": provenance,
        "corrections": corrections,
        "transitions": transitions,
    }
