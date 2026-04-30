"""Stop hook: context-window watchdog — write a handoff at threshold.

Fires on every Stop event. Reads context token usage from the current
session's JSONL file. When usage reaches GRADATA_CTX_THRESHOLD (default
0.65 = 65%), writes a structured handoff to
brain/sessions/handoff-{timestamp}.md and records the path in
brain/state/pending_handoff.txt.

On the next session start, inject_brain_rules reads pending_handoff.txt
and surfaces a <watchdog-alert> block so the LLM knows to review the
handoff and run /compact or /clear.

Register this hook BEFORE session_close in the Stop chain so the handoff
is written before graduation alters lessons.md.

Env vars:
    GRADATA_CTX_THRESHOLD  float 0.0-1.0, default 0.65
    GRADATA_CTX_WINDOW     int, model context limit in tokens, default 200000
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import sqlite3
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from gradata.hooks._base import resolve_brain_dir, run_hook
from gradata.hooks._profiles import Profile
logger = logging.getLogger(__name__)


_log = logging.getLogger(__name__)

HOOK_META = {
    "event": "Stop",
    "profile": Profile.MINIMAL,
    "timeout": 10000,
}

DEFAULT_THRESHOLD = 0.65
DEFAULT_CONTEXT_WINDOW = 200_000


# ── JSONL session file discovery ─────────────────────────────────────────────


def _find_session_jsonl(session_id: str | None) -> Path | None:
    """Locate the JSONL file for the current Claude Code session.

    Searches ~/.claude/projects/ for a file named {session_id}.jsonl.
    Falls back to the most recently modified JSONL if session_id is absent.
    """
    projects = Path.home() / ".claude" / "projects"
    if not projects.is_dir():
        return None
    try:
        all_dirs = [d for d in projects.iterdir() if d.is_dir()]
    except OSError:
        return None

    if session_id:
        for d in all_dirs:
            candidate = d / f"{session_id}.jsonl"
            if candidate.is_file():
                return candidate

    # Fallback: most recently modified JSONL across all project dirs.
    all_jsonls: list[Path] = []
    for d in all_dirs:
        with contextlib.suppress(OSError):
            all_jsonls.extend(f for f in d.iterdir() if f.suffix == ".jsonl")
    if not all_jsonls:
        return None
    return max(all_jsonls, key=lambda p: p.stat().st_mtime)


def _read_context_usage(jsonl_path: Path, context_window: int) -> float | None:
    """Return context usage ratio (0.0-1.0) from the last usage entry.

    Sums input_tokens + cache_read_input_tokens + cache_creation_input_tokens
    from the most recent assistant message entry. Returns None if usage
    can't be determined.
    """
    last_input: int | None = None
    try:
        with jsonl_path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(entry, dict):
                    continue
                # Format: {"type": "assistant", "message": {"usage": {...}}}
                msg = entry.get("message") or {}
                usage = msg.get("usage") if isinstance(msg, dict) else None
                # Also check top-level usage (some versions inline it).
                if not isinstance(usage, dict):
                    usage = entry.get("usage")
                if isinstance(usage, dict):
                    total = (
                        int(usage.get("input_tokens") or 0)
                        + int(usage.get("cache_read_input_tokens") or 0)
                        + int(usage.get("cache_creation_input_tokens") or 0)
                    )
                    if total > 0:
                        last_input = total
    except OSError:
        return None

    if last_input is None:
        return None
    return last_input / context_window


# ── Handoff content generation ────────────────────────────────────────────────


def _lesson_counts(brain_dir: Path) -> tuple[int, int, int]:
    """Return (instinct, pattern, rule) counts from lessons.md."""
    lessons_path = brain_dir / "lessons.md"
    if not lessons_path.is_file():
        return 0, 0, 0
    instinct = pattern = rule = 0
    try:
        for line in lessons_path.read_text(encoding="utf-8").splitlines():
            if "[INSTINCT:" in line:
                instinct += 1
            elif "[PATTERN:" in line:
                pattern += 1
            elif "[RULE:" in line:
                rule += 1
    except OSError:
        logger.warning('Suppressed exception in _lesson_counts', exc_info=True)
    return instinct, pattern, rule


def _recent_corrections(brain_dir: Path, limit: int = 10) -> list[str]:
    """Return the last N correction descriptions from system.db."""
    db = brain_dir / "system.db"
    if not db.is_file():
        return []
    rows: list[str] = []
    try:
        with sqlite3.connect(db) as conn:
            cursor = conn.execute(
                "SELECT data_json FROM events WHERE type = 'CORRECTION' ORDER BY ts DESC LIMIT ?",
                (limit,),
            )
            for (raw,) in cursor:
                try:
                    payload = json.loads(raw) if isinstance(raw, str) else {}
                    desc = payload.get("description") or payload.get("rule") or str(raw)[:80]
                    cat = payload.get("category", "")
                    rows.append(f"- [{cat}] {desc[:120]}" if cat else f"- {desc[:120]}")
                except (TypeError, json.JSONDecodeError):
                    rows.append(f"- {str(raw)[:80]}")
    except sqlite3.Error:
        logger.warning('Suppressed exception in _recent_corrections', exc_info=True)
    return rows


def _recent_commits(limit: int = 5) -> str:
    """Return recent git log --oneline from the current working dir."""
    with contextlib.suppress(Exception):
        result = subprocess.run(
            ["git", "log", f"-{limit}", "--oneline"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    return "(git log unavailable)"


def _build_handoff(
    brain_dir: Path,
    data: dict,
    ratio: float,
    used_tokens: int,
    context_window: int,
    session_id: str | None,
) -> str:
    ts = datetime.now(UTC).isoformat()
    session_num = data.get("session_number") or "unknown"
    instinct, pattern, rule = _lesson_counts(brain_dir)
    corrections = _recent_corrections(brain_dir)
    commits = _recent_commits()

    corrections_section = "\n".join(corrections) if corrections else "(none)"
    pct = int(ratio * 100)

    return f"""# Auto Handoff — {ts}

## Trigger
- Context window: **{pct}%** used ({used_tokens:,} / {context_window:,} tokens)
- Session: {session_num} | Session ID: {session_id or "unknown"}
- Written by: ctx_watchdog.py (threshold: {DEFAULT_THRESHOLD:.0%})

## Brain State at Handoff
- INSTINCT lessons: {instinct}
- PATTERN lessons: {pattern}
- RULE lessons: {rule}

## Recent Corrections (last 10)
{corrections_section}

## Recent Commits
{commits}

## Next Session
Read this file on session start. The context is fresh — continue from where
the previous session left off. Check `brain/loop-state.md` for open tasks.

Consider running `/compact` first to summarize the prior context, or `/clear`
to start fully fresh.
"""


# ── Pending handoff state ─────────────────────────────────────────────────────


def _write_pending(brain_dir: Path, handoff_path: Path) -> None:
    state_dir = brain_dir / "state"
    with contextlib.suppress(OSError):
        state_dir.mkdir(parents=True, exist_ok=True)
    try:
        (state_dir / "pending_handoff.txt").write_text(str(handoff_path), encoding="utf-8")
    except OSError as exc:
        _log.debug("ctx_watchdog: pending_handoff write failed: %s", exc)


# ── Main ─────────────────────────────────────────────────────────────────────


def main(data: dict) -> dict | None:
    threshold = float(os.environ.get("GRADATA_CTX_THRESHOLD", str(DEFAULT_THRESHOLD)))
    context_window = int(os.environ.get("GRADATA_CTX_WINDOW", str(DEFAULT_CONTEXT_WINDOW)))

    session_id = data.get("session_id") or data.get("sessionId")
    jsonl = _find_session_jsonl(session_id)
    if jsonl is None:
        return None

    ratio = _read_context_usage(jsonl, context_window)
    if ratio is None or ratio < threshold:
        return None

    brain_dir_str = resolve_brain_dir()
    if not brain_dir_str:
        return None
    brain_dir = Path(brain_dir_str)

    used_tokens = int(ratio * context_window)
    ts_slug = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%S")
    sessions_dir = brain_dir / "sessions"
    with contextlib.suppress(OSError):
        sessions_dir.mkdir(parents=True, exist_ok=True)

    handoff_path = sessions_dir / f"handoff-{ts_slug}.md"
    content = _build_handoff(brain_dir, data, ratio, used_tokens, context_window, session_id)

    try:
        handoff_path.write_text(content, encoding="utf-8")
        _write_pending(brain_dir, handoff_path)
        _log.info(
            "ctx_watchdog: context at %d%%, handoff written to %s",
            int(ratio * 100),
            handoff_path,
        )
    except OSError as exc:
        _log.debug("ctx_watchdog: handoff write failed: %s", exc)

    return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
