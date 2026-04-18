"""SessionStart hook: bump the session counter on fresh launches.

Claude Code has no real session counter. Events are tagged with whatever
``_detect_session()`` returns (MAX(session) from the events table), so
without a bump hook the counter sticks at its high-water mark forever —
every event gets lumped into the same session number.

This hook fires only on matcher=``startup`` (fresh claude-code launches).
``compact`` and ``resume`` are mid-session boundaries and must NOT bump.

The bump is a single SESSION_BOOT event written with ``session = MAX+1``.
No parsing, no stamp files — the event itself is the ground truth.
"""
from __future__ import annotations

import contextlib
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from gradata.hooks._base import resolve_brain_dir, run_hook
from gradata.hooks._profiles import Profile

_log = logging.getLogger(__name__)

HOOK_META = {
    "event": "SessionStart",
    "matcher": "startup",
    "profile": Profile.MINIMAL,
    "timeout": 3000,
}


def _next_session(db_path: Path) -> int:
    try:
        with contextlib.closing(sqlite3.connect(str(db_path))) as conn:
            row = conn.execute(
                "SELECT MAX(CAST(session AS INTEGER)) FROM events "
                "WHERE session IS NOT NULL"
            ).fetchone()
            current = int(row[0]) if row and row[0] is not None else 0
    except sqlite3.Error:
        current = 0
    return current + 1


def main(_data: dict) -> dict | None:
    brain_dir = resolve_brain_dir()
    if not brain_dir:
        return None

    db_path = Path(brain_dir) / "system.db"
    if not db_path.is_file():
        return None

    try:
        from gradata._events import emit
        from gradata._file_lock import platform_lock
        from gradata._paths import BrainContext

        # Serialize allocation + emit so concurrent launches never collide on
        # the same MAX(session) value and produce duplicate session numbers.
        lock_path = Path(brain_dir) / ".session_boot.lock"
        lock_path.touch(exist_ok=True)
        with open(lock_path, "r+b") as lock_fh, platform_lock(lock_fh, timeout=5.0):
            session = _next_session(db_path)
            ctx = BrainContext.from_brain_dir(brain_dir)
            emit(
                "SESSION_BOOT",
                source="hook:session_boot",
                data={
                    "session": session,
                    "ts": datetime.now(UTC).isoformat(),
                },
                ctx=ctx,
                session=session,
            )
    except Exception as e:
        _log.debug("session_boot skipped: %s", e)
    return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
