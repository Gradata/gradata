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
import os
import sys
from pathlib import Path

from gradata.hooks._profiles import Profile


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
    except (json.JSONDecodeError, Exception):
        return None


def output_result(result: str) -> None:
    print(json.dumps({"result": result}))


def output_block(reason: str) -> None:
    print(json.dumps({"decision": "block", "reason": reason}))


def get_brain():
    try:
        from gradata.brain import Brain
    except ImportError:
        return None
    brain_dir = os.environ.get("GRADATA_BRAIN_DIR") or os.environ.get("BRAIN_DIR")
    if not brain_dir:
        default = Path.home() / ".gradata" / "brain"
        if default.exists():
            brain_dir = str(default)
        else:
            return None
    try:
        p = Path(brain_dir)
        return Brain(brain_dir) if p.exists() else None
    except Exception:
        return None


def run_hook(main_fn, meta: dict, *, raw_input: str | None = None) -> None:
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
            print(json.dumps(result))
    except Exception:
        pass  # Silent — never break Claude Code
