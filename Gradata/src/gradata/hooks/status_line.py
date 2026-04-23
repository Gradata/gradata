"""Status-line command: prints a compact session summary for Claude Code.

Wire in ``~/.claude/settings.json``:

    "statusLine": {
        "type": "command",
        "command": "python -m gradata.hooks.status_line"
    }

Output format: ``s<session> | <lessons>R <patterns>P``

- ``session`` — count of JSONL files in ~/.claude/projects/<project-hash>/
              (the actual Claude Code session log count). Falls back to
              MAX(session) from the Gradata events DB if the project dir
              can't be located.
- ``R`` — graduated RULE count from lessons.md
- ``P`` — PATTERN count from lessons.md

Cheap enough to run on every status-line refresh. Silent-fails to a
minimal fallback so a broken brain never wedges the status bar.
"""

from __future__ import annotations

import contextlib
import sqlite3
import sys
from pathlib import Path

from gradata.hooks._base import resolve_brain_dir


def _brain_dir() -> Path | None:
    raw = resolve_brain_dir()
    if raw:
        p = Path(raw)
        return p if p.is_dir() else None
    return None


def _claude_project_dir() -> Path | None:
    """Find ~/.claude/projects/<hash>/ for the current working directory.

    Claude Code derives the project hash by replacing path separators, colons,
    and spaces with dashes: ``C:\\Users\\foo\\My Project`` → ``C--Users-foo-My-Project``.
    """
    try:
        cwd = Path.cwd()
    except OSError:
        return None
    project_hash = str(cwd).replace(":", "-").replace("\\", "-").replace("/", "-").replace(" ", "-")
    candidate = Path.home() / ".claude" / "projects" / project_hash
    return candidate if candidate.is_dir() else None


def _claude_session_count(project_dir: Path) -> int:
    """Count JSONL session files — each file is one Claude Code session."""
    try:
        return sum(1 for f in project_dir.iterdir() if f.suffix == ".jsonl")
    except OSError:
        return 0


def _fallback_session(db_path: Path) -> int:
    try:
        with contextlib.closing(sqlite3.connect(str(db_path))) as conn:
            row = conn.execute(
                "SELECT MAX(CAST(session AS INTEGER)) FROM events WHERE session IS NOT NULL"
            ).fetchone()
            if row and row[0] is not None:
                return int(row[0])
    except sqlite3.Error:
        pass
    return 0


def _rule_counts(lessons_path: Path) -> tuple[int, int]:
    if not lessons_path.is_file():
        return 0, 0
    rules = patterns = 0
    try:
        for line in lessons_path.read_text(encoding="utf-8").splitlines():
            if "[RULE:" in line:
                rules += 1
            elif "[PATTERN:" in line:
                patterns += 1
    except OSError:
        return 0, 0
    return rules, patterns


def main() -> int:
    brain = _brain_dir()
    if not brain:
        sys.stdout.write("gradata: no brain\n")
        return 0

    project_dir = _claude_project_dir()
    if project_dir:
        session = _claude_session_count(project_dir)
    else:
        session = _fallback_session(brain / "system.db")
    rules, patterns = _rule_counts(brain / "lessons.md")
    sys.stdout.write(f"s{session} | {rules}R {patterns}P\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
