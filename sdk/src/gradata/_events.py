"""
Unified event system for Gradata (SDK Copy).
=================================================
Dual-writes to events.jsonl (portable) and system.db (queryable).
Portable — uses _paths for all file locations.
"""

import contextlib
import json
import sqlite3
import sys
from datetime import UTC, datetime

# IMPORTANT: Use module reference (not value import) so set_brain_dir() updates propagate.
# `from X import Y` copies the value at import time — subsequent set_brain_dir() won't update it.
import gradata._paths as _p
from gradata._paths import BrainContext
from gradata._stats import brier_score, rolling_comparison, wilson_ci


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
    for col, defn in [("valid_from", "TEXT"), ("valid_until", "TEXT"), ("scope", "TEXT DEFAULT 'local'")]:
        try:
            conn.execute(f"ALTER TABLE events ADD COLUMN {col} {defn}")
        except sqlite3.OperationalError:
            pass
    conn.commit()


def emit(event_type: str, source: str, data: dict = None, tags: list = None,
         session: int = None, valid_from: str = None, valid_until: str = None,
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
        enriched_tags = enrich_tags(enriched_tags, event_type, data)
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
        print(f"[events] JSONL write failed: {e}", file=sys.stderr)

    try:
        with contextlib.closing(sqlite3.connect(str(db_path))) as conn:
            _ensure_table(conn)
            conn.execute(
                "INSERT INTO events (ts, session, type, source, data_json, tags_json, valid_from, valid_until) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (ts, session, event_type, source, json.dumps(data or {}),
                 json.dumps(enriched_tags), valid_from, valid_until),
            )
            conn.commit()
            sqlite_ok = True
    except Exception as e:
        print(f"[events] SQLite write failed: {e}", file=sys.stderr)

    if not jsonl_ok and not sqlite_ok:
        from gradata.exceptions import EventPersistenceError
        raise EventPersistenceError(
            f"Event {event_type} failed to persist to BOTH JSONL and SQLite. "
            "Learning data lost. Check file permissions and disk space."
        )

    event["_persisted"] = {"jsonl": jsonl_ok, "sqlite": sqlite_ok}
    return event


def emit_gate_result(gate_name: str, result: str, sources_checked: list = None, detail: str = "") -> dict:
    sources = sources_checked or []
    return emit("GATE_RESULT", "gate:execution", {
        "gate": gate_name, "result": result, "sources_checked": sources,
        "sources_complete": len(sources) > 0, "detail": detail,
    }, tags=[f"gate:{gate_name}"])


def emit_gate_override(gate_name: str, reason: str, steps_skipped: list = None) -> dict:
    return emit("GATE_OVERRIDE", "gate:override", {
        "gate": gate_name, "reason": reason,
        "steps_skipped": steps_skipped or [], "override_type": "explicit",
    }, tags=[f"gate:{gate_name}", "override:explicit"])


def query(event_type: str = None, session: int = None, last_n_sessions: int = None,
          limit: int = 100, as_of: str = None, active_only: bool = False,
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


def supersede(event_id: int, new_data: dict = None, new_tags: list = None,
              source: str = "supersede", new_valid_from: str = None):
    now = datetime.now(UTC).isoformat()
    with contextlib.closing(sqlite3.connect(str(_p.DB_PATH))) as conn:
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


def correction_rate(last_n_sessions: int = 5) -> dict:
    with contextlib.closing(sqlite3.connect(str(_p.DB_PATH))) as conn:
        _ensure_table(conn)
        rows = conn.execute("""
            SELECT session, COUNT(*) as count FROM events WHERE type = 'CORRECTION'
            AND session >= (SELECT COALESCE(MAX(session), 0) - ? FROM events)
            GROUP BY session ORDER BY session
        """, (last_n_sessions - 1,)).fetchall()
    return {r[0]: r[1] for r in rows}


def compute_leading_indicators(session: int) -> dict:
    with contextlib.closing(sqlite3.connect(str(_p.DB_PATH))) as conn:
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


def _ensure_periodic_audits(conn: sqlite3.Connection):
    """Create periodic_audits table if it doesn't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS periodic_audits (
            audit_name TEXT PRIMARY KEY,
            frequency INTEGER NOT NULL,
            last_run_session INTEGER DEFAULT 0,
            next_due_session INTEGER DEFAULT 0
        )
    """)
    conn.commit()


def find_contradictions(event_type: str = None, tag_prefix: str = None) -> list:
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


def audit_trend(last_n_sessions: int = 5) -> list:
    """Get audit scores for trend analysis."""
    with contextlib.closing(sqlite3.connect(str(_p.DB_PATH))) as conn:
        _ensure_table(conn)
        rows = conn.execute("""
            SELECT session, data_json FROM events
            WHERE type = 'AUDIT_SCORE'
            AND session >= (SELECT COALESCE(MAX(session), 0) - ? FROM events)
            ORDER BY session
        """, (last_n_sessions - 1,)).fetchall()
    return [{"session": r[0], "data": json.loads(r[1])} for r in rows]


def compute_brain_scores(last_n_prospect_sessions: int = 10) -> dict:
    """Compute the 3 Brain Report Card scores using Option B (rolling window, skip systems).

    Returns:
        system_health: 0-100% (all sessions)
        ai_quality: 0-100% (prospect sessions only)
        compound_growth: 0-100%+ indexed to industry baseline (prospect sessions only)
        last_prospect_session: int or None
    """
    with contextlib.closing(sqlite3.connect(str(_p.DB_PATH))) as conn:
        _ensure_table(conn)

        scores = {
            "system_health": 0.0,
            "ai_quality": 0.0,
            "compound_growth": 100.0,  # 100% = industry baseline
            "last_prospect_session": None,
            "data_sufficient": False,
            "score_errors": [],  # Track which components failed instead of silently zeroing
        }

        # --- System Health (all sessions) ---
        # Gate pass rate + event emission + tag coverage
        try:
            gates = conn.execute(
                "SELECT gate_pass_rate, gate_result FROM session_metrics ORDER BY session DESC LIMIT 10"
            ).fetchall()
            if gates:
                gate_passes = sum(1 for r in gates if r[1] == "PASS")
                gate_score = gate_passes / len(gates) if gates else 0

                # Event emission check
                recent_sessions = conn.execute(
                    "SELECT DISTINCT session FROM events ORDER BY session DESC LIMIT 10"
                ).fetchall()
                emission_score = len(recent_sessions) / 10 if recent_sessions else 0

                # Tag coverage: what % of OUTPUT events have complete tags?
                tagged_outputs = conn.execute(
                    "SELECT data_json FROM events WHERE type = 'OUTPUT' ORDER BY id DESC LIMIT 20"
                ).fetchall()
                tag_score = 1.0  # default perfect if no outputs yet
                if tagged_outputs:
                    complete = sum(1 for r in tagged_outputs
                                 if json.loads(r[0]).get("tags_complete", True))
                    tag_score = complete / len(tagged_outputs)

                scores["system_health"] = round(
                    (gate_score * 0.45 + emission_score * 0.30 + tag_score * 0.25) * 100, 1
                )
        except Exception as e:
            scores["score_errors"].append(f"system_health: {e}")

        # --- AI Quality (prospect sessions only) ---
        prospect_metrics = None
        try:
            prospect_metrics = conn.execute(
                "SELECT session, first_draft_acceptance, correction_density, confidence_calibration "
                "FROM session_metrics WHERE session_type = 'full' ORDER BY session DESC LIMIT ?",
                (last_n_prospect_sessions,)
            ).fetchall()

            if prospect_metrics:
                scores["last_prospect_session"] = prospect_metrics[0][0]

                acceptances = [r[1] for r in prospect_metrics if r[1] is not None]
                densities = [r[2] for r in prospect_metrics if r[2] is not None]
                calibrations = [r[3] for r in prospect_metrics if r[3] is not None]

                # Acceptance rate contribution (0-40 points)
                accept_score = (sum(acceptances) / len(acceptances) * 40) if acceptances else 20
                # Correction density contribution (0-30 points, inverted — lower is better)
                density_avg = sum(densities) / len(densities) if densities else 0.15
                density_score = max(0, (1 - density_avg / 0.30) * 30)
                # Calibration contribution — ONLY if real CALIBRATION events exist
                # No data = exclude from calculation (reweight), not fake a perfect score
                if calibrations:
                    cal_avg = sum(calibrations) / len(calibrations)
                    cal_score = cal_avg * 30
                    scores["ai_quality"] = round(min(100, accept_score + density_score + cal_score), 1)
                else:
                    # Reweight: acceptance 57%, density 43% (preserving ratio)
                    scores["ai_quality"] = round(min(100, (accept_score / 0.40) * 0.57 + (density_score / 0.30) * 0.43), 1)
                scores["data_sufficient"] = len(prospect_metrics) >= 3
        except Exception as e:
            scores["score_errors"].append(f"ai_quality: {e}")

        # --- Quality: absorb correction density trend (is AI improving?) ---
        try:
            if prospect_metrics and len(prospect_metrics) >= 4:
                first_half = prospect_metrics[len(prospect_metrics)//2:]  # older
                second_half = prospect_metrics[:len(prospect_metrics)//2]  # newer
                old_d = [r[2] for r in first_half if r[2] is not None]
                new_d = [r[2] for r in second_half if r[2] is not None]
                if old_d and new_d:
                    old_avg = sum(old_d) / len(old_d)
                    new_avg = sum(new_d) / len(new_d)
                    if new_avg < old_avg:
                        # Improving — bonus up to 10 points
                        improvement = min(10, ((old_avg - new_avg) / max(old_avg, 0.01)) * 20)
                        scores["ai_quality"] = round(min(100, scores["ai_quality"] + improvement), 1)
        except Exception as e:
            scores["score_errors"].append(f"density_trend_bonus: {e}")

        # --- Brier Score (self-scoring calibration accuracy) ---
        try:
            scored_outputs = conn.execute(
                "SELECT data_json FROM events WHERE type = 'OUTPUT' AND data_json LIKE '%self_score%' ORDER BY id"
            ).fetchall()
            predictions_and_outcomes = []
            for row in scored_outputs:
                d = json.loads(row[0]) if row[0] else {}
                self_score = d.get("self_score")
                if self_score is not None:
                    # Normalize self_score (typically 0-10) to 0-1 probability
                    prob = self_score / 10.0 if self_score > 1 else self_score
                    # Outcome: 1 = no correction (good), 0 = corrected
                    outcome = 0 if d.get("major_edit", False) else 1
                    predictions_and_outcomes.append((prob, outcome))

            brier = brier_score(predictions_and_outcomes)
            scores["brier_score"] = brier.get("score")
            scores["brier_calibration"] = brier.get("calibration", "NO_DATA")

            if brier.get("score") is not None:
                if brier["score"] < 0.10:
                    scores["ai_quality"] = round(min(100, scores["ai_quality"] + 10), 1)
                elif brier["score"] > 0.25:
                    scores["ai_quality"] = round(max(0, scores["ai_quality"] - 15), 1)
        except Exception:
            scores["brier_score"] = None
            scores["brier_calibration"] = "NO_DATA"

        # --- Agent Verification Quality ---
        try:
            verifications = conn.execute(
                "SELECT data_json FROM events WHERE type = 'VERIFICATION' "
                "AND valid_until IS NULL "
                "ORDER BY id DESC LIMIT 50"
            ).fetchall()
            if verifications:
                v_scores = []
                for v in verifications:
                    d = json.loads(v[0]) if v[0] else {}
                    overall = d.get("overall_score")
                    if overall is not None:
                        v_scores.append(overall)
                if v_scores:
                    avg_v = sum(v_scores) / len(v_scores)
                    # Scale to 0-10 bonus/penalty
                    v_bonus = (avg_v - 7) * 3  # 7 = neutral, 8 = +3, 6 = -3
                    scores["ai_quality"] = round(min(100, max(0, scores["ai_quality"] + v_bonus)), 1)
                    scores["agent_verification_avg"] = round(avg_v, 1)
                    scores["agent_verification_count"] = len(v_scores)
        except Exception as e:
            scores["score_errors"].append(f"agent_verification: {e}")

        # --- Wilson CI on key proportions ---
        try:
            if prospect_metrics:
                acceptances_raw = [r[1] for r in prospect_metrics if r[1] is not None]
                if acceptances_raw:
                    accept_successes = sum(1 for a in acceptances_raw if a >= 0.8)
                    scores["acceptance_ci"] = wilson_ci(accept_successes, len(acceptances_raw))
                densities_raw = [r[2] for r in prospect_metrics if r[2] is not None]
                if densities_raw:
                    low_density = sum(1 for d in densities_raw if d < 0.10)
                    scores["density_ci"] = wilson_ci(low_density, len(densities_raw))
        except Exception as e:
            scores["score_errors"].append(f"wilson_ci: {e}")

        # --- Rolling window trend on correction density ---
        try:
            all_densities = conn.execute(
                "SELECT correction_density FROM session_metrics WHERE correction_density IS NOT NULL ORDER BY session"
            ).fetchall()
            density_values = [r[0] for r in all_densities]
            if density_values:
                trend_result = rolling_comparison(density_values, window=10)
                # For correction density, lower is better, so invert the trend label
                raw_trend = trend_result.get("trend", "NO_DATA")
                if raw_trend == "IMPROVING":
                    # rolling_comparison says "improving" when recent > lifetime
                    # but for correction density, higher = worse
                    scores["density_trend"] = "DEGRADING"
                elif raw_trend == "DEGRADING":
                    scores["density_trend"] = "IMPROVING"
                else:
                    scores["density_trend"] = raw_trend
                scores["density_trend_pct"] = trend_result.get("pct_change", 0)
            else:
                scores["density_trend"] = "NO_DATA"
                scores["density_trend_pct"] = 0
        except Exception:
            scores["density_trend"] = "NO_DATA"
            scores["density_trend_pct"] = 0

        # --- Compound Growth (business outcomes vs industry baseline) ---
        # Domain-agnostic: tries CRM tables if they exist, falls back gracefully.
        # Baselines are configurable via brain config or env vars.
        has_growth_data = False
        try:
            import os
            _reply_baseline = float(os.environ.get("BRAIN_REPLY_BASELINE", "1.5"))
            _pipeline_baseline = float(os.environ.get("BRAIN_PIPELINE_BASELINE", "500"))
            _start_date_str = os.environ.get("BRAIN_START_DATE", "")

            # Auto-detect start date from first event if not configured
            if _start_date_str:
                _start_date = datetime.fromisoformat(_start_date_str)
            else:
                first_event = conn.execute(
                    "SELECT MIN(ts) FROM events WHERE ts IS NOT NULL"
                ).fetchone()
                _start_date = (datetime.fromisoformat(first_event[0].replace("Z", "+00:00").split("+")[0])
                              if first_event and first_event[0] else datetime.now())

            # 1. Reply rate from daily_metrics (if table exists)
            reply_index = 100.0
            try:
                reply_row = conn.execute(
                    "SELECT instantly_reply_rate FROM daily_metrics "
                    "WHERE instantly_reply_rate > 0 ORDER BY date DESC LIMIT 1"
                ).fetchone()
                if reply_row and reply_row[0]:
                    reply_index = (reply_row[0] / _reply_baseline) * 100
            except Exception:
                pass  # Table doesn't exist in non-sales brains — OK

            # 2. Pipeline build rate from pipeline_snapshots (if table exists)
            pipeline_index = 100.0
            try:
                pipeline_row = conn.execute(
                    "SELECT SUM(value) FROM pipeline_snapshots "
                    "WHERE stage NOT LIKE '%closed%' AND stage NOT LIKE '%lost%'"
                ).fetchone()
                if pipeline_row and pipeline_row[0] and pipeline_row[0] > 0:
                    total_pipeline = pipeline_row[0]
                    weeks_active = max(1, (datetime.now() - _start_date).days / 7)
                    pipeline_per_week = total_pipeline / weeks_active
                    pipeline_index = (pipeline_per_week / _pipeline_baseline) * 100
            except Exception:
                pass  # Table doesn't exist in non-sales brains — OK

            # 3. Deal velocity from deals table (if table exists)
            velocity_index = 100.0
            try:
                velocity_row = conn.execute(
                    "SELECT AVG(days_in_stage) FROM deals "
                    "WHERE stage NOT LIKE '%closed%' AND days_in_stage IS NOT NULL AND days_in_stage > 0"
                ).fetchone()
                if velocity_row and velocity_row[0]:
                    avg_days = velocity_row[0]
                    velocity_index = min(200, (30 / max(avg_days, 1)) * 100)
            except Exception:
                pass  # Table doesn't exist in non-sales brains — OK

            # Weighted: reply 30%, pipeline build 40%, velocity 30%
            scores["compound_growth"] = round(
                reply_index * 0.30 + pipeline_index * 0.40 + velocity_index * 0.30, 1
            )
            has_growth_data = True
        except Exception:
            has_growth_data = False

        if not has_growth_data:
            # Fallback: use pattern accumulation as a proxy until CRM data flows
            patterns_file = _p.BRAIN_DIR / "emails" / "PATTERNS.md"
            pattern_count = 0
            if patterns_file.exists():
                import re as _re
                content = patterns_file.read_text(encoding="utf-8")
                pattern_count = len(_re.findall(r'\[(?:PROVEN|EMERGING|HYPOTHESIS)\]', content))
            # Patterns are knowledge, not outcomes — cap bonus at 15%
            scores["compound_growth"] = round(100 + min(15, pattern_count * 1.5), 1)

        # --- Architecture Quality (all sessions, downstream utilization) ---
        # Measures: did systems work get used in subsequent sessions? Did it break anything?
        try:
            # Get systems sessions and their gate results
            sys_sessions = conn.execute(
                "SELECT session, gate_result FROM session_metrics WHERE session_type = 'systems' ORDER BY session DESC LIMIT 10"
            ).fetchall()

            if sys_sessions:
                # Regression rate: systems sessions that were followed by a gate FAIL
                regressions = 0
                for ss in sys_sessions:
                    next_session = conn.execute(
                        "SELECT gate_result FROM session_metrics WHERE session > ? ORDER BY session LIMIT 1",
                        (ss[0],)
                    ).fetchone()
                    if next_session and next_session[0] == "FAIL":
                        regressions += 1

                regression_rate = regressions / len(sys_sessions) if sys_sessions else 0
                # Score: 100% = no regressions, -20% per regression
                arch_score = max(0, (1 - regression_rate) * 100)

                # Bonus: if system health is high, architecture is contributing
                if scores["system_health"] >= 80:
                    arch_score = min(100, arch_score + 10)

                scores["arch_quality"] = round(arch_score, 1)
            else:
                scores["arch_quality"] = 0.0
        except Exception:
            scores["arch_quality"] = 0.0

    return scores
