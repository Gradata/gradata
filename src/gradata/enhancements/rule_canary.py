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

from __future__ import annotations

import logging
import sqlite3
from datetime import UTC
from enum import Enum
from pathlib import Path

_log = logging.getLogger(__name__)

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


def _get_db_path(ctx=None) -> Path:
    """Resolve DB path from context, env var, or relative traversal.

    Resolution order:
      1. BrainContext.db_path (if ctx provided)
      2. BRAIN_DIR environment variable + /system.db
      3. Relative traversal from this file's location

    Raises:
        ValueError: If no database path can be resolved.
    """
    import os

    # 1. DI context
    if ctx is not None:
        db = getattr(ctx, "db_path", None)
        if db and Path(db).exists():
            return Path(db)

    # 2. Environment variable
    env_dir = os.environ.get("BRAIN_DIR")
    if env_dir:
        p = Path(env_dir) / "system.db"
        if p.exists():
            return p

    # 3. Relative traversal (SDK installed alongside brain)
    try:
        scripts_dir = Path(__file__).resolve().parent.parent.parent.parent.parent / "brain"
        p = scripts_dir / "system.db"
        if p.exists():
            return p
    except Exception:
        pass

    raise ValueError("Cannot resolve rule_canary DB path: no context, BRAIN_DIR, or relative path found")


def promote_to_canary(rule_category: str, session: int, db_path: Path | None = None) -> None:
    """Mark a newly graduated rule as canary. Tracks start session."""
    if db_path is None:
        db_path = _get_db_path()

    try:
        from datetime import datetime
        now = datetime.now(UTC).isoformat()

        with sqlite3.connect(str(db_path)) as conn:
            _ensure_table(conn)
            conn.execute(
                "INSERT OR REPLACE INTO rule_canary (category, status, start_session, correction_count, updated_at) "
                "VALUES (?, ?, ?, 0, ?)",
                (rule_category, CanaryStatus.CANARY.value, session, now),
            )
            conn.commit()
    except Exception as e:
        _log.warning("promote_to_canary failed: %s", e)


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
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            _ensure_table(conn)

            row = conn.execute(
                "SELECT * FROM rule_canary WHERE category = ?",
                (rule_category,),
            ).fetchone()

            if not row:
                return {
                    "status": "not_found",
                    "sessions_active": 0,
                    "corrections_caused": 0,
                    "recommendation": "not_in_canary",
                }

            status = row["status"]
            start_session = row["start_session"]
            sessions_active = session - start_session + 1

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
        _log.warning("check_canary_health failed: %s", e)
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
        from datetime import datetime
        now = datetime.now(UTC).isoformat()

        with sqlite3.connect(str(db_path)) as conn:
            _ensure_table(conn)
            conn.execute(
                "UPDATE rule_canary SET status = ?, updated_at = ? WHERE category = ?",
                (CanaryStatus.ROLLED_BACK.value, now, rule_category),
            )
            conn.commit()

        # Emit RULE_ROLLBACK event
        try:
            from gradata._events import emit
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
            _log.warning("rollback_rule emit failed: %s", e)

    except Exception as e:
        _log.warning("rollback_rule failed: %s", e)


def promote_to_active(rule_category: str, db_path: Path | None = None) -> None:
    """Promote a canary rule to fully active after healthy canary period."""
    if db_path is None:
        db_path = _get_db_path()

    try:
        from datetime import datetime
        now = datetime.now(UTC).isoformat()

        with sqlite3.connect(str(db_path)) as conn:
            _ensure_table(conn)
            conn.execute(
                "UPDATE rule_canary SET status = ?, updated_at = ? WHERE category = ?",
                (CanaryStatus.ACTIVE.value, now, rule_category),
            )
            conn.commit()

        # Emit CANARY_PROMOTED event
        try:
            from gradata._events import emit
            emit(
                "CANARY_PROMOTED",
                "rule_canary:promote_to_active",
                {"rule_category": rule_category},
                tags=[f"category:{rule_category}", "canary:promoted"],
            )
        except Exception as e:
            _log.warning("promote_to_active emit failed: %s", e)

    except Exception as e:
        _log.warning("promote_to_active failed: %s", e)


def get_canary_rules(db_path: Path | None = None) -> list[dict]:
    """List all rules currently in canary status."""
    if db_path is None:
        db_path = _get_db_path()

    try:
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            _ensure_table(conn)

            rows = conn.execute(
                "SELECT * FROM rule_canary WHERE status = ?",
                (CanaryStatus.CANARY.value,),
            ).fetchall()

        return [dict(r) for r in rows]

    except Exception as e:
        _log.warning("get_canary_rules failed: %s", e)
        return []
