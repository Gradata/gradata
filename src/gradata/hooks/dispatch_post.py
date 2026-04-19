"""Consolidated PostToolUse dispatcher.

Replaces three separate hook invocations (auto_correct, tool_finding_capture,
tool_failure_emit) with a single Python process. On Windows each fresh
interpreter cold-start is ~200-500ms, so collapsing 3 spawns into 1 saves
~0.5-1s per Edit/Bash and reduces stdout noise.

Routing is matcher-aware: only hooks whose matcher includes the active
tool_name are invoked. This preserves the per-hook matcher semantics that
the previous settings.json layout enforced.

Output is merged: ``result`` strings concatenate (newline-joined), other
fields take the last writer. If every constituent returns ``None``, the
dispatcher emits nothing.

Settings.json migration: replace the auto_correct + tool_finding_capture +
tool_failure_emit hook entries with a single entry pointing here. Keep
``generated_runner_post`` separate (it shells out to user-installed hooks
with its own timeout discipline).
"""

from __future__ import annotations

import logging

from ._base import run_hook
from ._base import Profile

_log = logging.getLogger(__name__)

HOOK_META = {
    "event": "PostToolUse",
    "matcher": "Bash|Edit|Write",
    "profile": Profile.STANDARD,
    "timeout": 8000,
}

# Tool -> module names. Imports are deferred to main() so a failing import
# in one constituent doesn't block the others.
_ROUTING: dict[str, tuple[str, ...]] = {
    "Edit": ("auto_correct", "tool_finding_capture"),
    "Write": ("auto_correct", "tool_finding_capture"),
    "MultiEdit": ("auto_correct", "tool_finding_capture"),
    "Bash": ("tool_failure_emit", "tool_finding_capture"),
}


def _invoke(module_name: str, data: dict) -> dict | None:
    """Import and invoke a constituent hook's main(). Suppress all errors."""
    try:
        module = __import__(f"gradata.hooks.{module_name}", fromlist=["main"])
        return module.main(data)
    except Exception as exc:
        _log.debug("dispatch_post: %s suppressed exception: %s", module_name, exc)
        return None


def main(data: dict) -> dict | None:
    tool_name = data.get("tool_name") or data.get("tool") or ""
    handlers = _ROUTING.get(tool_name, ())
    if not handlers:
        return None

    result_parts: list[str] = []
    merged: dict = {}
    for module_name in handlers:
        out = _invoke(module_name, data)
        if not out:
            continue
        if out.get("result"):
            result_parts.append(str(out["result"]))
        for k, v in out.items():
            if k != "result":
                merged[k] = v

    if result_parts:
        merged["result"] = "\n".join(result_parts)
    return merged or None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
