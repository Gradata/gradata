"""
Rule Canary — Graduated rules run in canary mode for 3 sessions before full activation.

When a rule graduates (PATTERN -> RULE), it enters canary mode. If it causes
regressions (corrections in its category) during the canary period, it gets
auto-rolled back to INSTINCT confidence.

SQLite table: rule_canary (category PK, status, start_session, correction_count)

Usage:
    from gradata.enhancements.rule_canary import (
        promote_to_canary, check_canary_health, rollback_rule, get_canary_rules,
    )
"""

import json
import sqlite3
import sys
from enum import Enum
from pathlib import Path

# Default canary period: 3 sessions
CANARY_SESSIONS = 3
# Rollback target confidence (back to INSTINCT range)
ROLLBACK_CONFIDENCE = 0.50


class CanaryStatus(Enum):
    CANARY = "canary"           # first 3 sessions after graduation
    ACTIVE = "active"           # passed canary period
    ROLLED_BACK = "rolled_back"  # caused regression, disabled


_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS rule_canary (
    category TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'canary',
    start_session INTEGER NOT NULL,
    correction_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT
)
"""


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(_CREATE_TABLE_SQL)
    conn.commit()


def _get_db_path() -> Path:
    """Resolve DB path, supporting both SDK and brain/scripts contexts."""
    try:
        scripts_dir = Path(__file__).resolve().parent.parent.parent.parent.parent / "brain"
        # Check common locations
        candidates = [
            Path("C:/Users/olive/SpritesWork/brain/system.db"),
            scripts_dir / "system.db",
        ]
        for c in candidates:
            if c.exists():
                return c
        return candidates[0]  # default
    except Exception:
        return Path("C:/Users/olive/SpritesWork/brain/system.db")


def promote_to_canary(rule_category: str, session: int, db_path: Path | None = None) -> None:
    """Mark a newly graduated rule as canary. Tracks start session."""
    if db_path is None:
        db_path = _get_db_path()

    try:
        conn = sqlite3.connect(str(db_path))
        _ensure_table(conn)

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        conn.execute(
            "INSERT OR REPLACE INTO rule_canary (category, status, start_session, correction_count, updated_at) "
            "VALUES (?, ?, ?, 0, ?)",
            (rule_category, CanaryStatus.CANARY.value, session, now),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"WARNING [promote_to_canary]: {e}", file=sys.stderr)


def check_canary_health(rule_category: str, session: int, db_path: Path | None = None) -> dict:
    """Check if canary rule is healthy after N sessions.

    Returns:
        {status, sessions_active, corrections_caused, recommendation}
        Healthy: 0 corrections in its category over 3 sessions -> promote to ACTIVE
        Unhealthy: 1+ corrections in its category -> recommend ROLLBACK
    """
    if db_path is None:
        db_path = _get_db_path()

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        _ensure_table(conn)

        row = conn.execute(
            "SELECT * FROM rule_canary WHERE category = ?",
            (rule_category,),
        ).fetchone()

        if not row:
            conn.close()
            return {
                "status": "not_found",
                "sessions_active": 0,
                "corrections_caused": 0,
                "recommendation": "not_in_canary",
            }

        status = row["status"]
        start_session = row["start_session"]
        sessions_active = session - start_session

        # Count corrections in this category since canary started
        correction_count = 0
        try:
            corr_row = conn.execute(
                "SELECT COUNT(*) as cnt FROM events WHERE type = 'CORRECTION' "
                "AND data_json LIKE ? AND CAST(session AS INTEGER) >= ?",
                (f'%"{rule_category}"%', start_session),
            ).fetchone()
            if corr_row:
                correction_count = corr_row["cnt"]
        except Exception:
            # events table may not exist in test contexts
            correction_count = row["correction_count"]

        # Update correction count
        conn.execute(
            "UPDATE rule_canary SET correction_count = ? WHERE category = ?",
            (correction_count, rule_category),
        )
        conn.commit()
        conn.close()

        # Determine recommendation
        if status in (CanaryStatus.ACTIVE.value, CanaryStatus.ROLLED_BACK.value):
            recommendation = "already_resolved"
        elif correction_count > 0:
            recommendation = "ROLLBACK"
        elif sessions_active >= CANARY_SESSIONS:
            recommendation = "PROMOTE"
        else:
            recommendation = "WAIT"

        return {
            "status": status,
            "sessions_active": sessions_active,
            "corrections_caused": correction_count,
            "recommendation": recommendation,
        }

    except Exception as e:
        print(f"WARNING [check_canary_health]: {e}", file=sys.stderr)
        return {
            "status": "error",
            "sessions_active": 0,
            "corrections_caused": 0,
            "recommendation": "error",
            "error": str(e),
        }


def rollback_rule(rule_category: str, reason: str, db_path: Path | None = None) -> None:
    """Roll back a rule: demote confidence to 0.50 (back to INSTINCT range),
    log RULE_ROLLBACK event."""
    if db_path is None:
        db_path = _get_db_path()

    try:
        conn = sqlite3.connect(str(db_path))
        _ensure_table(conn)

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        conn.execute(
            "UPDATE rule_canary SET status = ?, updated_at = ? WHERE category = ?",
            (CanaryStatus.ROLLED_BACK.value, now, rule_category),
        )
        conn.commit()
        conn.close()

        # Emit RULE_ROLLBACK event
        try:
            # Try brain/scripts events.py first (fast path)
            scripts_dir = Path("C:/Users/olive/SpritesWork/brain/scripts")
            if scripts_dir.exists():
                sys.path.insert(0, str(scripts_dir))
            from events import emit
            emit(
                "RULE_ROLLBACK",
                "rule_canary:rollback_rule",
                {
                    "rule_category": rule_category,
                    "reason": reason,
                    "rollback_confidence": ROLLBACK_CONFIDENCE,
                },
                tags=[f"category:{rule_category}", "canary:rollback"],
            )
        except Exception as e:
            print(f"WARNING [rollback_rule/emit]: {e}", file=sys.stderr)

    except Exception as e:
        print(f"WARNING [rollback_rule]: {e}", file=sys.stderr)


def promote_to_active(rule_category: str, db_path: Path | None = None) -> None:
    """Promote a canary rule to fully active after healthy canary period."""
    if db_path is None:
        db_path = _get_db_path()

    try:
        conn = sqlite3.connect(str(db_path))
        _ensure_table(conn)

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        conn.execute(
            "UPDATE rule_canary SET status = ?, updated_at = ? WHERE category = ?",
            (CanaryStatus.ACTIVE.value, now, rule_category),
        )
        conn.commit()
        conn.close()

        # Emit CANARY_PROMOTED event
        try:
            scripts_dir = Path("C:/Users/olive/SpritesWork/brain/scripts")
            if scripts_dir.exists():
                sys.path.insert(0, str(scripts_dir))
            from events import emit
            emit(
                "CANARY_PROMOTED",
                "rule_canary:promote_to_active",
                {"rule_category": rule_category},
                tags=[f"category:{rule_category}", "canary:promoted"],
            )
        except Exception as e:
            print(f"WARNING [promote_to_active/emit]: {e}", file=sys.stderr)

    except Exception as e:
        print(f"WARNING [promote_to_active]: {e}", file=sys.stderr)


def get_canary_rules(db_path: Path | None = None) -> list[dict]:
    """List all rules currently in canary status."""
    if db_path is None:
        db_path = _get_db_path()

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        _ensure_table(conn)

        rows = conn.execute(
            "SELECT * FROM rule_canary WHERE status = ?",
            (CanaryStatus.CANARY.value,),
        ).fetchall()
        conn.close()

        return [dict(r) for r in rows]

    except Exception as e:
        print(f"WARNING [get_canary_rules]: {e}", file=sys.stderr)
        return []
