"""Claude Code hooks integration — auto-capture corrections from Claude Code sessions.

Installs a hook into Claude Code's settings.json that calls brain.correct()
when the user edits Claude's output (Edit/Write tool diffs).

Usage:
    gradata hooks install     # Add hook to ~/.claude/settings.json
    gradata hooks uninstall   # Remove hook
    gradata hooks status      # Check if hook is installed
"""

from __future__ import annotations

import json
import sys


def install_hook(profile: str = "standard") -> None:
    """Add Gradata hooks to Claude Code settings."""
    from ._installer import install
    install(profile)


def uninstall_hook() -> None:
    """Remove Gradata hooks from Claude Code settings."""
    from ._installer import uninstall
    uninstall()


def hook_status() -> None:
    """Check if Gradata hooks are installed."""
    from ._installer import status
    status()


def capture_correction() -> None:
    """Called by Claude Code hook — reads stdin for tool use context and records correction."""
    import logging
    _log = logging.getLogger("gradata.hooks")

    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        payload = json.loads(raw)
    except Exception:
        return  # Silent — never block Claude Code

    tool_name = payload.get("tool_name", "")
    if tool_name not in ("Edit", "Write"):
        return

    # Extract draft (old content) and final (new content) from tool input/output
    tool_input = payload.get("tool_input", {})
    payload.get("tool_output", "")

    old_string = tool_input.get("old_string", "")
    new_string = tool_input.get("new_string", "")

    if not old_string or not new_string or old_string == new_string:
        return

    from ._base import resolve_brain_dir
    brain_dir = resolve_brain_dir()
    if not brain_dir:
        return

    try:
        from .. import Brain
        brain = Brain(brain_dir)
        brain.correct(draft=old_string, final=new_string, category="CODE")
        _log.debug("Captured correction from Claude Code hook")
    except Exception as e:
        _log.debug("Hook capture failed: %s", e)


# ---------------------------------------------------------------------------
# CLI entry point (called by Claude Code hook)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if "--capture" in sys.argv:
        capture_correction()
