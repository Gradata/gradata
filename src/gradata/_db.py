"""
Database Helpers — Shared SQLite utilities for all Gradata modules.
===================================================================
Single source of truth for database connection management, table
creation, WAL mode configuration, and file locking.

Usage::

    from gradata._db import get_connection, ensure_tables
    from gradata._db import lessons_lock

    conn = get_connection(db_path)
    ensure_tables(conn)  # creates all standard tables

    with lessons_lock(lessons_path):
        lessons_path.write_text(content)
"""

from __future__ import annotations

import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


def get_connection(db_path: str | Path, wal: bool = True) -> sqlite3.Connection:
    """Get a SQLite connection with standard Gradata settings.

    Args:
        db_path: Path to the SQLite database file.
        wal: Enable WAL journal mode (default True for concurrent reads).

    Returns:
        sqlite3.Connection with WAL mode and busy timeout configured.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    if wal:
        conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def ensure_table(conn: sqlite3.Connection, create_sql: str) -> None:
    """Execute a CREATE TABLE IF NOT EXISTS statement.

    Args:
        conn: Active SQLite connection.
        create_sql: The full CREATE TABLE SQL statement.
    """
    conn.execute(create_sql)
    conn.commit()


# ---------------------------------------------------------------------------
# File Locking — concurrency protection for lessons.md
# ---------------------------------------------------------------------------

@contextmanager
def lessons_lock(lessons_path: str | Path, timeout: float = 10.0):
    """Context manager for exclusive file lock on lessons.md.

    Uses a .lock file with platform-appropriate locking (msvcrt on Windows,
    fcntl on Unix). Falls back to atomic lockfile if neither is available.

    Usage::

        with lessons_lock(brain_dir / "lessons.md"):
            text = lessons_path.read_text()
            # ... modify ...
            lessons_path.write_text(new_text)

    Args:
        lessons_path: Path to lessons.md (lock file is .lessons.lock alongside it).
        timeout: Max seconds to wait for lock (default 10).
    """
    lock_path = Path(lessons_path).parent / ".lessons.lock"
    fd = None
    deadline = time.monotonic() + timeout

    try:
        # Open/create the lock file
        fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)

        # Platform-specific locking
        if os.name == "nt":
            import msvcrt
            while True:
                try:
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        raise TimeoutError(
                            f"Could not acquire lessons lock after {timeout}s"
                        )
                    time.sleep(0.1)
        else:
            import fcntl
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        raise TimeoutError(
                            f"Could not acquire lessons lock after {timeout}s"
                        )
                    time.sleep(0.1)

        yield lock_path

    finally:
        if fd is not None:
            # Release lock
            if os.name == "nt":
                try:
                    import msvcrt
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            else:
                try:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_UN)
                except OSError:
                    pass
            os.close(fd)


def write_lessons_safe(lessons_path: str | Path, content: str) -> None:
    """Write to lessons.md with file locking for concurrency safety.

    Acquires an exclusive lock before writing. If the lock can't be
    acquired within 10 seconds, raises TimeoutError.
    """
    p = Path(lessons_path)
    with lessons_lock(p):
        p.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Credit Budgets — daily API spend limits for autonomous agents
# ---------------------------------------------------------------------------

_CREDIT_BUDGETS_SQL = """
CREATE TABLE IF NOT EXISTS credit_budgets (
    api_name TEXT PRIMARY KEY,
    daily_limit INTEGER NOT NULL DEFAULT 50,
    used_today INTEGER NOT NULL DEFAULT 0,
    last_reset TEXT NOT NULL DEFAULT '',
    cost_per_call REAL NOT NULL DEFAULT 1.0,
    notes TEXT DEFAULT ''
)
"""

_DEFAULT_BUDGETS: list[tuple[str, int, int, str, float, str]] = [
    # Override with your own vendor budgets via ensure_credit_budgets() + INSERT.
    # Examples:
    # ("openai", 100, 0, "", 1.0, "OpenAI API calls"),
    # ("anthropic", 50, 0, "", 1.0, "Anthropic API calls"),
]


def ensure_credit_budgets(conn: sqlite3.Connection) -> int:
    """Create credit_budgets table and seed defaults if empty.

    Returns:
        Number of default rows inserted (0 if table already populated).
    """
    conn.execute(_CREDIT_BUDGETS_SQL)
    count = conn.execute("SELECT COUNT(*) FROM credit_budgets").fetchone()[0]
    if count == 0:
        conn.executemany(
            "INSERT OR IGNORE INTO credit_budgets "
            "(api_name, daily_limit, used_today, last_reset, cost_per_call, notes) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            _DEFAULT_BUDGETS,
        )
        conn.commit()
        return len(_DEFAULT_BUDGETS)
    return 0


def check_budget(conn: sqlite3.Connection, api_name: str, count: int = 1) -> dict:
    """Check if an API call is within daily budget.

    Resets used_today if last_reset is not today. Returns dict with
    'allowed', 'remaining', 'daily_limit', 'used_today'.

    Args:
        conn: Active SQLite connection.
        api_name: API identifier (e.g. "service-a", "service-b").
        count: Number of calls to check (default 1).
    """
    from datetime import date

    today = date.today().isoformat()

    row = conn.execute(
        "SELECT daily_limit, used_today, last_reset FROM credit_budgets WHERE api_name = ?",
        (api_name,),
    ).fetchone()

    if row is None:
        return {"allowed": True, "remaining": 999, "daily_limit": 999, "used_today": 0,
                "api_name": api_name, "error": "unknown API — no budget configured"}

    limit, used, last_reset = row[0], row[1], row[2]

    # Reset if new day
    if last_reset != today:
        conn.execute(
            "UPDATE credit_budgets SET used_today = 0, last_reset = ? WHERE api_name = ?",
            (today, api_name),
        )
        conn.commit()
        used = 0

    remaining = max(0, limit - used)
    allowed = remaining >= count

    return {
        "allowed": allowed,
        "remaining": remaining,
        "daily_limit": limit,
        "used_today": used,
        "api_name": api_name,
    }


def spend_budget(conn: sqlite3.Connection, api_name: str, count: int = 1) -> dict:
    """Record API usage against the daily budget.

    Checks budget first, then increments used_today if allowed.
    Returns same dict as check_budget with updated counts.
    """
    result = check_budget(conn, api_name, count)
    if not result["allowed"]:
        return result

    from datetime import date
    today = date.today().isoformat()

    conn.execute(
        "UPDATE credit_budgets SET used_today = used_today + ?, last_reset = ? WHERE api_name = ?",
        (count, today, api_name),
    )
    conn.commit()

    result["used_today"] += count
    result["remaining"] -= count
    return result


def budget_summary(conn: sqlite3.Connection) -> list[dict]:
    """Return all budget rows for morning brief reporting."""
    from datetime import date
    today = date.today().isoformat()

    # Reset stale rows first
    conn.execute(
        "UPDATE credit_budgets SET used_today = 0, last_reset = ? WHERE last_reset != ?",
        (today, today),
    )
    conn.commit()

    rows = conn.execute(
        "SELECT api_name, daily_limit, used_today, cost_per_call, notes "
        "FROM credit_budgets ORDER BY api_name"
    ).fetchall()

    return [
        {
            "api_name": r[0],
            "daily_limit": r[1],
            "used_today": r[2],
            "cost_per_call": r[3],
            "notes": r[4],
            "remaining": r[1] - r[2],
        }
        for r in rows
    ]