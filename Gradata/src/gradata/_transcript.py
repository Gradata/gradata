"""Layer 0: lightweight turn logger for retroactive feedback mining.

log_turn() appends conversation turns to
brain/sessions/{session_id}/transcript.jsonl so that session_close can
run the implicit_feedback regex sweep retroactively across the full
session, catching signals the real-time UserPromptSubmit hook may have
missed (e.g. turns that arrived too fast or during hook downtime).

Opt-in only. Disabled unless GRADATA_TRANSCRIPT=1.

Non-Anthropic middleware (wrap_openai, LangChainCallback, CrewAIGuard)
calls log_turn() because those providers have no native session log.
wrap_anthropic does NOT call log_turn() — Claude Code's native JSONL at
~/.claude/projects/{hash}/{session_id}.jsonl is the authoritative source.

PII policy:
  - Assistant content is truncated at GRADATA_TRANSCRIPT_TRUNCATE (2000 chars).
  - Non-text tool_use / image content is logged as {has_non_text: true}.
  - No redaction of user content (caller is responsible).
  - Files are TTL-cleaned by cleanup_ttl().
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

_log = logging.getLogger(__name__)

DEFAULT_TRUNCATE = 2000
DEFAULT_TTL_DAYS = 30
_ENABLED_ENV = "GRADATA_TRANSCRIPT"
_TRUNCATE_ENV = "GRADATA_TRANSCRIPT_TRUNCATE"
_TTL_ENV = "GRADATA_TRANSCRIPT_TTL_DAYS"


def _is_enabled() -> bool:
    return os.environ.get(_ENABLED_ENV, "0") == "1"


def _session_dir(brain_dir: str, session_id: str) -> Path:
    return Path(brain_dir) / "sessions" / session_id


def _transcript_path(brain_dir: str, session_id: str) -> Path:
    return _session_dir(brain_dir, session_id) / "transcript.jsonl"


def log_turn(
    brain_dir: str,
    session_id: str,
    role: str,
    content: str | None,
    *,
    has_non_text: bool = False,
    truncate_at: int | None = None,
) -> None:
    """Append one conversation turn to the session transcript.

    Silently no-ops when GRADATA_TRANSCRIPT != 1, or on any write error.
    Content is truncated to avoid bloating the transcript with long assistant
    responses; the retroactive sweep only needs the user-role turns anyway.
    """
    if not _is_enabled():
        return
    if not brain_dir or not session_id:
        return

    limit = (
        truncate_at
        if truncate_at is not None
        else int(os.environ.get(_TRUNCATE_ENV, str(DEFAULT_TRUNCATE)))
    )

    entry: dict = {
        "ts": datetime.now(UTC).isoformat(),
        "role": role,
    }
    if has_non_text:
        entry["has_non_text"] = True
        entry["content"] = None
    elif content is not None:
        entry["content"] = content[:limit] if len(content) > limit else content
    else:
        entry["content"] = None

    try:
        path = _transcript_path(brain_dir, session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as exc:
        _log.debug("transcript log_turn failed: %s", exc)


def load_turns(brain_dir: str, session_id: str) -> list[dict]:
    """Load all turns from a Gradata-written transcript.jsonl.

    Returns an empty list on any read error or if the file doesn't exist.
    """
    path = _transcript_path(brain_dir, session_id)
    if not path.is_file():
        return []
    turns: list[dict] = []
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    turns.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return turns


def cleanup_ttl(brain_dir: str, ttl_days: int | None = None) -> int:
    """Delete transcript directories older than ttl_days. Returns count deleted."""
    days = (
        ttl_days if ttl_days is not None else int(os.environ.get(_TTL_ENV, str(DEFAULT_TTL_DAYS)))
    )
    now = datetime.now(UTC).timestamp()
    cutoff = now - days * 86400
    sessions_dir = Path(brain_dir) / "sessions"
    if not sessions_dir.is_dir():
        return 0

    deleted = 0
    for session_dir in sessions_dir.iterdir():
        if not session_dir.is_dir():
            continue
        transcript = session_dir / "transcript.jsonl"
        if not transcript.is_file():
            continue
        try:
            mtime = transcript.stat().st_mtime
            if mtime < cutoff:
                transcript.unlink(missing_ok=True)
                deleted += 1
        except OSError:
            continue
    return deleted
