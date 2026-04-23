"""Shared hook protocol for Gradata SDK hooks.

Every hook module follows this pattern:
    from gradata.hooks._base import run_hook
    from gradata.hooks._profiles import Profile

    HOOK_META = {"event": "PreToolUse", "matcher": "Write", "profile": Profile.STANDARD, ...}
    def main(data: dict) -> dict | None: ...
    if __name__ == "__main__": run_hook(main, HOOK_META)
"""

from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gradata.brain import Brain
import sys
from pathlib import Path

from gradata.hooks._profiles import Profile

_log = logging.getLogger(__name__)


def get_profile() -> Profile:
    raw = os.environ.get("GRADATA_HOOK_PROFILE", "standard").lower().strip()
    mapping = {"minimal": Profile.MINIMAL, "standard": Profile.STANDARD, "strict": Profile.STRICT}
    return mapping.get(raw, Profile.STANDARD)


def should_run(min_profile: Profile) -> bool:
    return get_profile() >= min_profile


def read_input(raw: str) -> dict | None:
    if not raw or not raw.strip():
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def output_result(result: str) -> None:
    print(json.dumps({"result": result}))


def output_block(reason: str) -> None:
    print(json.dumps({"decision": "block", "reason": reason}))


def resolve_brain_dir() -> str | None:
    """Resolve brain directory from env vars or default location."""
    brain_dir = os.environ.get("GRADATA_BRAIN_DIR") or os.environ.get("BRAIN_DIR")
    if brain_dir:
        return brain_dir if Path(brain_dir).exists() else None
    default = Path.home() / ".gradata" / "brain"
    return str(default) if default.exists() else None


def extract_message(data: dict) -> str | None:
    """Extract user message from hook stdin data."""
    msg = data.get("message") or data.get("prompt") or data.get("content") or ""
    if not isinstance(msg, str):
        return None
    msg = msg.strip()
    return msg if msg else None


def get_brain() -> Brain | None:
    """Get a Brain instance from resolved brain dir, or None on failure."""
    try:
        from gradata.brain import Brain
    except ImportError:
        return None
    brain_dir = resolve_brain_dir()
    if not brain_dir:
        return None
    try:
        return Brain(brain_dir)
    except Exception:
        return None


def _record_telemetry(meta: dict, hook_name: str, payload: str | None) -> None:
    """Best-effort: append one JSONL line with bytes-out per hook invocation.

    Disabled when ``GRADATA_TELEMETRY=off``. Failures are silent — telemetry
    must never break a hook.
    """
    if os.environ.get("GRADATA_TELEMETRY", "on").lower() == "off":
        return
    try:
        brain_dir = resolve_brain_dir()
        if not brain_dir:
            return
        import time

        line = json.dumps(
            {
                "ts": time.time(),
                "event": meta.get("event", "?"),
                "hook": hook_name,
                "bytes": len(payload or ""),
            }
        )
        log_path = Path(brain_dir) / "telemetry.jsonl"
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def run_hook(main_fn, meta: dict, *, raw_input: str | None = None) -> None:
    payload: str | None = None
    try:
        min_profile = meta.get("profile", Profile.STANDARD)
        if not should_run(min_profile):
            return
        raw = raw_input if raw_input is not None else sys.stdin.read()
        data = read_input(raw)
        if data is None and meta.get("event") not in ("SessionStart", "Stop", "PreCompact"):
            return
        result = main_fn(data or {})
        if result:
            payload = json.dumps(result)
            print(payload)
    except Exception as exc:
        _log.debug("Hook %s suppressed exception: %s", meta.get("event", "?"), exc)
    finally:
        hook_name = getattr(main_fn, "__module__", "?").rsplit(".", 1)[-1]
        _record_telemetry(meta, hook_name, payload)
