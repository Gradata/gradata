"""
Unified event system for Gradata (SDK Copy).
=================================================
Dual-writes to events.jsonl (portable) and system.db (queryable).
Portable — uses _paths for all file locations.
"""

from __future__ import annotations

import contextlib
import json
import logging
import sqlite3
import sys
from datetime import UTC, datetime

# IMPORTANT: Use module reference (not value import) so set_brain_dir() updates propagate.
# `from X import Y` copies the value at import time — subsequent set_brain_dir() won't update it.
import gradata._paths as _p
from gradata._paths import BrainContext
from gradata._stats import brier_score

_log = logging.getLogger("gradata.events")


def _ensure_table(conn: sqlite3.Connection):
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            session INTEGER,
            type TEXT NOT NULL,
            source TEXT,
            data_json TEXT,
            tags_json TEXT,
            valid_from TEXT,
            valid_until TEXT,
            scope TEXT DEFAULT 'local'
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_session ON events(session)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_session_type ON events(session, type)")
    try:
        conn.execute("ALTER TABLE events ADD COLUMN valid_from TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE events ADD COLUMN valid_until TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE events ADD COLUMN scope TEXT DEFAULT 'local'")
    except sqlite3.OperationalError:
        pass
    conn.commit()


def emit(event_type: str, source: str, data: dict | None = None, tags: list | None = None,
         session: int | None = None, valid_from: str | None = None, valid_until: str | None = None,
         ctx: "BrainContext | None" = None):
    """Emit an event to the brain's event log.

    Args:
        ctx: Optional BrainContext for path resolution. If None, falls back to
             module-level globals (backward compat).
    """
    # Resolve paths: prefer explicit ctx, fall back to globals
    events_jsonl = ctx.events_jsonl if ctx else _p.EVENTS_JSONL
    db_path = ctx.db_path if ctx else _p.DB_PATH

    ts = datetime.now(UTC).isoformat()
    if session is None:
        session = _detect_session(ctx=ctx)

    if valid_from is None:
        valid_from = ts

    enriched_tags = tags or []
    try:
        from gradata._tag_taxonomy import enrich_tags, validate_tags
        enriched_tags = enrich_tags(enriched_tags, event_type, data or {})
        issues = validate_tags(enriched_tags, event_type)
        if issues:
            import logging
            _logger = logging.getLogger("gradata.events")
            for issue in issues[:2]:
                _logger.debug("tag validation: %s", issue)
    except ImportError:
        pass

    event = {
        "ts": ts, "session": session, "type": event_type, "source": source,
        "data": data or {}, "tags": enriched_tags,
        "valid_from": valid_from, "valid_until": valid_until,
    }

    # Dual-write: JSONL (portable) + SQLite (queryable).
    # At least ONE must succeed or we raise — learning data loss is unacceptable.
    jsonl_ok = False
    sqlite_ok = False

    try:
        with open(events_jsonl, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        jsonl_ok = True
    except Exception as e:
        _log.error("JSONL write failed: %s", e)

    try:
        with contextlib.closing(sqlite3.connect(str(db_path))) as conn:
            _ensure_table(conn)
            cursor = conn.execute(
                "INSERT INTO events (ts, session, type, source, data_json, tags_json, valid_from, valid_until) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (ts, session, event_type, source, json.dumps(data or {}),
                 json.dumps(enriched_tags), valid_from, valid_until),
            )
            event["id"] = cursor.lastrowid
            conn.commit()
            sqlite_ok = True
    except Exception as e:
        _log.error("SQLite write failed: %s", e)

    if not jsonl_ok and not sqlite_ok:
        from gradata.exceptions import EventPersistenceError
        raise EventPersistenceError(
            f"Event {event_type} failed to persist to BOTH JSONL and SQLite. "
            "Learning data lost. Check file permissions and disk space."
        )

    event["_persisted"] = {"jsonl": jsonl_ok, "sqlite": sqlite_ok}
    return event



def emit_gate_result(gate_name: str, result: str, sources_checked: list | None = None, detail: str = "") -> dict:
    sources = sources_checked or []
    return emit("GATE_RESULT", "gate:execution", {
        "gate": gate_name, "result": result, "sources_checked": sources,
        "sources_complete": len(sources) > 0, "detail": detail,
    }, tags=[f"gate:{gate_name}"])


def emit_gate_override(gate_name: str, reason: str, steps_skipped: list | None = None) -> dict:
    return emit("GATE_OVERRIDE", "gate:override", {
        "gate": gate_name, "reason": reason,
        "steps_skipped": steps_skipped or [], "override_type": "explicit",
    }, tags=[f"gate:{gate_name}", "override:explicit"])


def query(event_type: str | None = None, session: int | None = None, last_n_sessions: int | None = None,
          limit: int = 100, as_of: str | None = None, active_only: bool = False,
          ctx: "BrainContext | None" = None) -> list:
    db_path = ctx.db_path if ctx else _p.DB_PATH
    with contextlib.closing(sqlite3.connect(str(db_path))) as conn:
        conn.row_factory = sqlite3.Row
        _ensure_table(conn)

        where_clauses = []
        params = []

        if event_type:
            where_clauses.append("type = ?")
            params.append(event_type)
        if session is not None:
            where_clauses.append("session = ?")
            params.append(session)
        if last_n_sessions:
            where_clauses.append("session >= (SELECT MAX(session) - ? FROM events)")
            params.append(last_n_sessions - 1)
        if as_of:
            where_clauses.append("(valid_from IS NULL OR valid_from <= ?)")
            params.append(as_of)
            where_clauses.append("(valid_until IS NULL OR valid_until > ?)")
            params.append(as_of)
        if active_only:
            where_clauses.append("valid_until IS NULL")

        where = " AND ".join(where_clauses) if where_clauses else "1=1"
        params.append(limit)

        rows = conn.execute(
            f"SELECT * FROM events WHERE {where} ORDER BY id DESC LIMIT ?", params
        ).fetchall()

    return [
        {
            "id": r["id"], "ts": r["ts"], "session": r["session"],
            "type": r["type"], "source": r["source"],
            "data": json.loads(r["data_json"]) if r["data_json"] else {},
            "tags": json.loads(r["tags_json"]) if r["tags_json"] else [],
            "valid_from": r["valid_from"], "valid_until": r["valid_until"],
        }
        for r in rows
    ]


def supersede(event_id: int, new_data: dict | None = None, new_tags: list | None = None,
              source: str = "supersede", new_valid_from: str | None = None,
              ctx: "BrainContext | None" = None):
    now = datetime.now(UTC).isoformat()
    db = ctx.db_path if ctx else _p.DB_PATH
    with contextlib.closing(sqlite3.connect(str(db))) as conn:
        conn.row_factory = sqlite3.Row
        _ensure_table(conn)
        original = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if not original:
            return None
        conn.execute("UPDATE events SET valid_until = ? WHERE id = ?", (now, event_id))
        conn.commit()
    orig_tags = json.loads(original["tags_json"]) if original["tags_json"] else []
    replacement = emit(
        event_type=original["type"], source=source,
        data=new_data or (json.loads(original["data_json"]) if original["data_json"] else {}),
        tags=new_tags or orig_tags, session=_detect_session(), valid_from=new_valid_from or now,
    )
    replacement["superseded_id"] = event_id
    return replacement


def correction_rate(last_n_sessions: int = 5, ctx: "BrainContext | None" = None) -> dict:
    db = ctx.db_path if ctx else _p.DB_PATH
    with contextlib.closing(sqlite3.connect(str(db))) as conn:
        _ensure_table(conn)
        rows = conn.execute("""
            SELECT session, COUNT(*) as count FROM events WHERE type = 'CORRECTION'
            AND session >= (SELECT COALESCE(MAX(session), 0) - ? FROM events)
            GROUP BY session ORDER BY session
        """, (last_n_sessions - 1,)).fetchall()
    return {r[0]: r[1] for r in rows}


def compute_leading_indicators(session: int, ctx: "BrainContext | None" = None) -> dict:
    db = ctx.db_path if ctx else _p.DB_PATH
    with contextlib.closing(sqlite3.connect(str(db))) as conn:
        _ensure_table(conn)
        result = {
            "first_draft_acceptance": 0.0, "correction_density": 0.0,
            "avg_time_to_deliverable_ms": 0.0, "source_coverage": 0.0,
            "confidence_calibration": 1.0,
        }
        outputs = conn.execute(
            "SELECT data_json FROM events WHERE type = 'OUTPUT' AND session = ?", (session,)
        ).fetchall()
        if outputs:
            total = len(outputs)
            unedited = sum(1 for r in outputs if not json.loads(r[0]).get("major_edit", False))
            result["first_draft_acceptance"] = unedited / total if total > 0 else 0.0

        corrections = conn.execute(
            "SELECT COUNT(*) FROM events WHERE type = 'CORRECTION' AND session = ?", (session,)
        ).fetchone()[0]
        output_count = len(outputs) if outputs else 0
        result["correction_density"] = min(corrections / output_count, 1.0) if output_count > 0 else 0.0

        gates = conn.execute(
            "SELECT data_json FROM events WHERE type = 'GATE_RESULT' AND session = ?", (session,)
        ).fetchall()
        if gates:
            total_gates = len(gates)
            complete = sum(1 for r in gates if json.loads(r[0]).get("sources_complete", False))
            result["source_coverage"] = complete / total_gates if total_gates > 0 else 0.0

        calibrations = conn.execute(
            "SELECT data_json FROM events WHERE type = 'CALIBRATION' AND session = ?", (session,)
        ).fetchall()
        if calibrations:
            # Support both formats:
            #   v1 (sessions <= 6): {"delta": -1, "self_score": 7, "user_score": 6}
            #   v2 (sessions 15+):  {"brier_score": 0.0625, "calibration_rating": "EXCELLENT", "predictions": [...]}
            brier_events = []
            delta_events = []
            for r in calibrations:
                d = json.loads(r[0])
                if "brier_score" in d and d["brier_score"] is not None:
                    brier_events.append(d)
                elif "delta" in d:
                    delta_events.append(d)

            if brier_events:
                # v2 format: use Brier score directly
                # Brier < 0.25 is "within range" (good calibration)
                # Convert to 0-1 scale: 1.0 = perfect, 0.0 = terrible
                avg_brier = sum(e["brier_score"] for e in brier_events) / len(brier_events)
                result["confidence_calibration"] = round(max(0.0, 1.0 - avg_brier), 4)
            elif delta_events:
                # v1 format: delta-based (legacy)
                total_cal = len(delta_events)
                within_range = sum(1 for d in delta_events if abs(d.get("delta", 0)) <= 2)
                result["confidence_calibration"] = within_range / total_cal if total_cal > 0 else 1.0

    return result


def get_current_session() -> int:
    """Public alias for session detection. Used by brain.track_rule()."""
    return _detect_session()


def _detect_session(ctx: "BrainContext | None" = None) -> int:
    """Detect current session number from event data.

    Args:
        ctx: Optional BrainContext. Falls back to module globals if None.

    Strategy (most reliable first):
    1. Query MAX(session) from events table (works for any brain)
    2. Read loop-state.md if it exists (backward compat with legacy runtime)
    3. Return 0 as fallback
    """
    db_path = ctx.db_path if ctx else _p.DB_PATH
    brain_dir = ctx.brain_dir if ctx else _p.BRAIN_DIR

    # Strategy 1: DB query — works for any brain with events
    try:
        with contextlib.closing(sqlite3.connect(str(db_path))) as conn:
            row = conn.execute(
                "SELECT MAX(CAST(session AS INTEGER)) FROM events WHERE session IS NOT NULL"
            ).fetchone()
            if row and row[0] is not None:
                return int(row[0])
    except Exception:
        pass

    # Strategy 2: loop-state.md (backward compat)
    import re
    loop_state = brain_dir / "loop-state.md"
    if loop_state.exists():
        try:
            text = loop_state.read_text(encoding="utf-8")
            m = re.search(r"Session\s+(\d+)", text)
            if m:
                return int(m.group(1))
        except Exception:
            pass

    return 0


# ── Brain-quality functions (promoted from brain shim) ────────────────



def find_contradictions(event_type: str | None = None, tag_prefix: str | None = None) -> list:
    """Find events that may contradict each other — same tags, overlapping validity.

    Useful for detecting stale-but-not-expired facts (e.g., two active events
    about the same prospect's timeline).

    Args:
        event_type: Filter to specific event type
        tag_prefix: Filter to events with tags starting with this prefix (e.g., "prospect:")

    Returns:
        List of conflicting event pairs with overlap details
    """
    events = query(event_type=event_type, active_only=True, limit=500)

    if tag_prefix:
        events = [e for e in events if any(t.startswith(tag_prefix) for t in e.get("tags", []))]

    conflicts = []
    for i, a in enumerate(events):
        for b in events[i + 1:]:
            # Check tag overlap
            shared_tags = set(a.get("tags", [])) & set(b.get("tags", []))
            if shared_tags and a["type"] == b["type"]:
                conflicts.append({
                    "event_a": {"id": a["id"], "ts": a["ts"], "data": a["data"]},
                    "event_b": {"id": b["id"], "ts": b["ts"], "data": b["data"]},
                    "shared_tags": list(shared_tags),
                    "both_active": a.get("valid_until") is None and b.get("valid_until") is None,
                })

    return conflicts


def audit_trend(last_n_sessions: int = 5, ctx: "BrainContext | None" = None) -> list:
    """Get audit scores for trend analysis."""
    db = ctx.db_path if ctx else _p.DB_PATH
    with contextlib.closing(sqlite3.connect(str(db))) as conn:
        _ensure_table(conn)
        rows = conn.execute("""
            SELECT session, data_json FROM events
            WHERE type = 'AUDIT_SCORE'
            AND session >= (SELECT COALESCE(MAX(session), 0) - ? FROM events)
            ORDER BY session
        """, (last_n_sessions - 1,)).fetchall()
    return [{"session": r[0], "data": json.loads(r[1])} for r in rows]

