"""
Unified event system for Gradata.
====================================
Dual-writes to events.jsonl (portable) and system.db (queryable).
"""

from __future__ import annotations

import contextlib
import json
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

# IMPORTANT: Use module reference (not value import) so set_brain_dir() updates propagate.
# `from X import Y` copies the value at import time — subsequent set_brain_dir() won't update it.
import gradata._paths as _p
from gradata._platform import detect_platform_source

if TYPE_CHECKING:
    from gradata._paths import BrainContext

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
    # Dedup guard: (ts, type, source) uniquely identifies an event for the
    # purposes of retry-safe idempotent writes. RetainOrchestrator also uses
    # this key in its cursor, so the constraint and the orchestrator stay in
    # lockstep. Pre-existing duplicate rows (if any) are preserved -- the
    # index is created with IF NOT EXISTS on a fresh key set.
    with contextlib.suppress(sqlite3.OperationalError):
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_events_dedup "
            "ON events(ts, type, source)"
        )
    with contextlib.suppress(sqlite3.OperationalError):
        conn.execute("ALTER TABLE events ADD COLUMN valid_from TEXT")
    with contextlib.suppress(sqlite3.OperationalError):
        conn.execute("ALTER TABLE events ADD COLUMN valid_until TEXT")
    with contextlib.suppress(sqlite3.OperationalError):
        conn.execute("ALTER TABLE events ADD COLUMN scope TEXT DEFAULT 'local'")
    conn.commit()


def emit(event_type: str, source: str, data: dict | None = None, tags: list | None = None,
         session: int | None = None, valid_from: str | None = None, valid_until: str | None = None,
         ctx: BrainContext | None = None):
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

    # Enrich data dict with auto-detected platform source (env-var based).
    # Keeps public API signatures untouched — callers get this for free.
    # Always copy so we never mutate the caller's dict in place.
    data = dict(data) if data else {}
    data.setdefault("platform_source", detect_platform_source())

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
            # INSERT OR IGNORE + UNIQUE(ts,type,source) makes emit() idempotent
            # across retries and partial-write recoveries. If an identical
            # event was already persisted (same dedup key), the INSERT is a
            # no-op -- we then look up the pre-existing row's id so callers
            # that depend on `event["id"]` still get the real rowid.
            cursor = conn.execute(
                "INSERT OR IGNORE INTO events (ts, session, type, source, data_json, tags_json, valid_from, valid_until) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (ts, session, event_type, source, json.dumps(data or {}),
                 json.dumps(enriched_tags), valid_from, valid_until),
            )
            if cursor.rowcount == 1:
                event["id"] = cursor.lastrowid
            else:
                existing = conn.execute(
                    "SELECT id FROM events WHERE ts=? AND type=? AND source=?",
                    (ts, event_type, source),
                ).fetchone()
                event["id"] = existing[0] if existing else None
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
          ctx: BrainContext | None = None) -> list:
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
              ctx: BrainContext | None = None):
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
        tags=new_tags or orig_tags, session=_detect_session(ctx=ctx), valid_from=new_valid_from or now,
        ctx=ctx,
    )
    replacement["superseded_id"] = event_id
    return replacement


def correction_rate(last_n_sessions: int = 5, ctx: BrainContext | None = None) -> dict:
    db = ctx.db_path if ctx else _p.DB_PATH
    with contextlib.closing(sqlite3.connect(str(db))) as conn:
        _ensure_table(conn)
        rows = conn.execute("""
            SELECT session, COUNT(*) as count FROM events WHERE type = 'CORRECTION'
            AND session >= (SELECT COALESCE(MAX(session), 0) - ? FROM events)
            GROUP BY session ORDER BY session
        """, (last_n_sessions - 1,)).fetchall()
    return {r[0]: r[1] for r in rows}


def compute_leading_indicators(session: int, ctx: BrainContext | None = None) -> dict:
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


def _detect_session(ctx: BrainContext | None = None) -> int:
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


def audit_trend(last_n_sessions: int = 5, ctx: BrainContext | None = None) -> list:
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


# ── 3-Phase Retain Orchestrator (adapted from Hindsight's retain pattern) ────


class RetainOrchestrator:
    """3-phase event persistence adapted from Hindsight's retain orchestrator.

    Phase 1 (read, separate connection): Load existing state, compute delta
        — identify which queued events are already persisted so interrupted
        writes never duplicate data.
    Phase 2 (atomic, single pass): Append new events to events.jsonl and
        INSERT OR IGNORE into system.db in one contiguous write.
    Phase 3 (best-effort, post-commit): Non-critical work — manifest updates,
        index refreshes. Failure here never rolls back Phase 2.

    Crash recovery: .event_cursor.json tracks the last successfully committed
    event's ``ts+type`` key so an interrupted flush resumes from the correct
    position on the next call.
    """

    def __init__(self, brain_dir: str | Path) -> None:
        from pathlib import Path as _Path
        self.brain_dir = _Path(brain_dir)
        self.events_path = self.brain_dir / "events.jsonl"
        self.db_path = self.brain_dir / "system.db"
        self._cursor_path = self.brain_dir / ".event_cursor.json"
        self._pending: list[dict] = []
        self._last_committed_key: str | None = self._load_cursor()

    # ── cursor helpers ──────────────────────────────────────────────────

    @staticmethod
    def _event_key(event: dict) -> str:
        """Stable dedup key for an event: ts + type + source."""
        return f"{event.get('ts', '')}|{event.get('type', '')}|{event.get('source', '')}"

    def _load_cursor(self) -> str | None:
        if self._cursor_path.is_file():
            try:
                data = json.loads(self._cursor_path.read_text(encoding="utf-8"))
                return data.get("last_committed_key")
            except Exception:
                pass
        return None

    def _save_cursor(self, key: str) -> None:
        try:
            self._cursor_path.write_text(
                json.dumps({"last_committed_key": key}),
                encoding="utf-8",
            )
            self._last_committed_key = key
        except Exception as exc:
            _log.warning("RetainOrchestrator: failed to save cursor: %s", exc)

    # ── public API ──────────────────────────────────────────────────────

    def queue(self, event: dict) -> None:
        """Queue an event dict for batch persistence on the next flush()."""
        self._pending.append(event)

    @property
    def pending_count(self) -> int:
        """Number of events waiting to be flushed."""
        return len(self._pending)

    def flush(self) -> dict:
        """Execute 3-phase persistence for all queued events.

        Returns a result dict::

            {
                "written": int,       # events successfully appended
                "errors": list[str],  # non-fatal errors from any phase
                "phases": {
                    "read":  {"existing_keys": int, "new": int},
                    "write": {"events_written": int},
                    "post":  {"manifest_updated": bool},
                }
            }
        """
        if not self._pending:
            return {"written": 0, "errors": [], "phases": {}}

        result: dict = {"written": 0, "errors": [], "phases": {}}

        # ── Phase 1: Read — compute delta ───────────────────────────────
        existing_keys: set[str] = set()
        try:
            if self.events_path.is_file():
                for raw_line in self.events_path.read_text(encoding="utf-8").splitlines():
                    raw_line = raw_line.strip()
                    if raw_line:
                        try:
                            evt = json.loads(raw_line)
                            existing_keys.add(self._event_key(evt))
                        except json.JSONDecodeError:
                            continue
            result["phases"]["read"] = {
                "existing_keys": len(existing_keys),
                "new": sum(
                    1 for e in self._pending
                    if self._event_key(e) not in existing_keys
                ),
            }
        except Exception as exc:
            result["errors"].append(f"Phase 1: {exc}")
            # Fall through with empty existing_keys — safer than aborting

        new_events = [
            e for e in self._pending
            if self._event_key(e) not in existing_keys
        ]

        if not new_events:
            self._pending.clear()
            return result

        # ── Phase 2: Atomic write ────────────────────────────────────────
        try:
            # 2a: Append to events.jsonl
            with self.events_path.open("a", encoding="utf-8") as fh:
                for event in new_events:
                    fh.write(json.dumps(event, default=str, ensure_ascii=False) + "\n")
                    result["written"] += 1

            # 2b: INSERT OR IGNORE into system.db (same schema as emit())
            if self.db_path.is_file():
                try:
                    with contextlib.closing(sqlite3.connect(str(self.db_path))) as conn:
                        _ensure_table(conn)
                        conn.execute("PRAGMA busy_timeout=5000")
                        for event in new_events:
                            conn.execute(
                                "INSERT OR IGNORE INTO events "
                                "(ts, session, type, source, data_json, tags_json, "
                                " valid_from, valid_until) "
                                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                (
                                    event.get("ts", ""),
                                    event.get("session"),
                                    event.get("type", ""),
                                    event.get("source", ""),
                                    json.dumps(event.get("data", {}), default=str),
                                    json.dumps(event.get("tags", []), default=str),
                                    event.get("valid_from"),
                                    event.get("valid_until"),
                                ),
                            )
                        conn.commit()
                except Exception as db_exc:
                    result["errors"].append(f"Phase 2 DB: {db_exc}")

            # Save cursor after successful JSONL write
            last_key = self._event_key(new_events[-1])
            self._save_cursor(last_key)

            result["phases"]["write"] = {"events_written": result["written"]}

        except Exception as exc:
            result["errors"].append(f"Phase 2: {exc}")
            self._pending.clear()
            return result  # Phase 3 must not run if Phase 2 failed

        # ── Phase 3: Best-effort post-commit work ────────────────────────
        manifest_updated = False
        try:
            try:
                from gradata._brain_manifest import update_manifest  # type: ignore[import]
                update_manifest(self.brain_dir)
                manifest_updated = True
            except (ImportError, Exception):
                pass
        except Exception as exc:
            result["errors"].append(f"Phase 3: {exc}")

        result["phases"]["post"] = {"manifest_updated": manifest_updated}

        self._pending.clear()
        return result


# ── Module-level singleton so hot paths can queue without re-constructing ────

_ORCHESTRATORS: dict[str, RetainOrchestrator] = {}


def get_retain_orchestrator(brain_dir: str | Path) -> RetainOrchestrator:
    """Return a cached RetainOrchestrator keyed by brain_dir.

    Use for batch scenarios (session_close, graduation sweeps) where we want
    atomic multi-event flush with crash-recovery. For single-event writes,
    use :func:`emit` directly -- it has INSERT OR IGNORE dedup built in.
    """
    key = str(brain_dir)
    orch = _ORCHESTRATORS.get(key)
    if orch is None:
        orch = RetainOrchestrator(brain_dir)
        _ORCHESTRATORS[key] = orch
    return orch


def flush_retain(brain_dir: str | Path) -> dict:
    """Flush any queued events for brain_dir. Safe to call when queue is empty."""
    orch = _ORCHESTRATORS.get(str(brain_dir))
    if orch is None or orch.pending_count == 0:
        return {"written": 0, "errors": [], "phases": {}}
    return orch.flush()
