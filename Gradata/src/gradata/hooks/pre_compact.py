"""PreCompact hook: handoff-as-summary on auto-compact; snapshot on manual.

When CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=65 fires auto-compact and ctx_watchdog
has written a pending handoff, this hook replaces the compact summary with
the handoff content verbatim. The compact mechanism becomes the trigger;
the handoff is the payload. Post-compact SessionStart receives a clean
context where the handoff is the only history — functionally identical to
/clear + handoff injection, but fully automatic.

For manual /compact (no pending handoff), falls back to saving a snapshot.
"""

from __future__ import annotations
import logging

import contextlib
import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from gradata.hooks._base import resolve_brain_dir, run_hook
from gradata.hooks._profiles import Profile
logger = logging.getLogger(__name__)


HOOK_META = {
    "event": "PreCompact",
    "matcher": "manual|auto",
    "profile": Profile.STANDARD,
    "timeout": 5000,
}


def _read_pending_handoff(brain_dir: Path) -> tuple[str, Path] | tuple[None, None]:
    """Return (content, pending_path) if a ctx_watchdog handoff is staged."""
    pending = brain_dir / "state" / "pending_handoff.txt"
    if not pending.is_file():
        return None, None
    try:
        handoff_path = Path(pending.read_text(encoding="utf-8").strip())
        if handoff_path.is_file():
            content = handoff_path.read_text(encoding="utf-8").strip()
            if content:
                return content, pending
    except OSError:
        logger.warning('Suppressed exception in _read_pending_handoff', exc_info=True)
    return None, None


def _save_snapshot(brain_dir: Path, trigger: str) -> None:
    snapshot: dict = {
        "timestamp": datetime.now(UTC).isoformat(),
        "compact_type": trigger,
        "brain_dir": str(brain_dir),
    }
    lessons_path = brain_dir / "lessons.md"
    if lessons_path.is_file():
        with contextlib.suppress(OSError):
            text = lessons_path.read_text(encoding="utf-8")
            snapshot["lesson_count"] = sum(
                1 for ln in text.splitlines() if ln.strip() and not ln.startswith("#")
            )
    try:
        uid: str | int = os.getuid() if hasattr(os, "getuid") else os.getlogin()
    except OSError:
        uid = f"pid{os.getpid()}"
    user_tmp = Path(tempfile.gettempdir()) / f"gradata-{uid}"
    with contextlib.suppress(OSError):
        user_tmp.mkdir(parents=True, exist_ok=True)
    dir_hash = hashlib.md5(str(brain_dir).encode()).hexdigest()[:8]
    snap_path = user_tmp / f"compact-snapshot-{dir_hash}.json"
    with contextlib.suppress(OSError):
        snap_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")


def main(data: dict) -> dict | None:
    try:
        brain_dir_str = resolve_brain_dir()
        if not brain_dir_str:
            return None
        brain_dir = Path(brain_dir_str)

        # Claude Code sends "trigger" field; older versions used "type".
        trigger = (data.get("trigger") or data.get("type") or "unknown") if data else "unknown"

        if trigger == "auto":
            handoff_content, pending_path = _read_pending_handoff(brain_dir)
            if handoff_content and pending_path:
                # Consume pending_handoff.txt so inject_brain_rules doesn't also alert.
                with contextlib.suppress(OSError):
                    pending_path.unlink(missing_ok=True)
                return {
                    "result": (
                        "COMPACT INSTRUCTIONS: Discard all conversation history. "
                        "Your entire summary must consist ONLY of the following "
                        "handoff document, reproduced verbatim — no additions, "
                        "no omissions, no preamble:\n\n"
                        f"{handoff_content}"
                    )
                }

        _save_snapshot(brain_dir, trigger)
        return {"result": "State saved before compaction"}

    except Exception:
        return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
