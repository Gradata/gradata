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
import os
import sys
from pathlib import Path

_HOOK_NAME = "gradata-capture"
_SETTINGS_PATH = Path.home() / ".claude" / "settings.json"

# The hook command that Claude Code will execute
_HOOK_COMMAND = (
    f"{sys.executable} -m gradata.hooks.claude_code --capture"
)

_HOOK_CONFIG = {
    "type": "PostToolUse",
    "matcher": "Edit|Write",
    "command": _HOOK_COMMAND,
}


def install_hook() -> None:
    """Add Gradata correction capture hook to Claude Code settings."""
    settings = _load_settings()
    hooks = settings.setdefault("hooks", {})
    hooks[_HOOK_NAME] = _HOOK_CONFIG
    _save_settings(settings)
    print(f"Gradata hook installed in {_SETTINGS_PATH}")
    print(f"Hook will capture corrections on Edit/Write tool use.")


def uninstall_hook() -> None:
    """Remove Gradata hook from Claude Code settings."""
    settings = _load_settings()
    hooks = settings.get("hooks", {})
    if _HOOK_NAME in hooks:
        del hooks[_HOOK_NAME]
        _save_settings(settings)
        print("Gradata hook removed.")
    else:
        print("Gradata hook not found in settings.")


def hook_status() -> None:
    """Check if the Gradata hook is installed."""
    settings = _load_settings()
    hooks = settings.get("hooks", {})
    if _HOOK_NAME in hooks:
        print(f"Gradata hook: INSTALLED")
        print(f"  Settings: {_SETTINGS_PATH}")
        print(f"  Command: {hooks[_HOOK_NAME].get('command', '?')}")
    else:
        print("Gradata hook: NOT INSTALLED")
        print(f"  Run: gradata hooks install")


def capture_correction() -> None:
    """Called by Claude Code hook — reads stdin for tool use context and records correction."""
    import logging
    _log = logging.getLogger("gradata.hooks")

    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        payload = json.loads(raw)
    except (json.JSONDecodeError, Exception):
        return  # Silent — never block Claude Code

    tool_name = payload.get("tool_name", "")
    if tool_name not in ("Edit", "Write"):
        return

    # Extract draft (old content) and final (new content) from tool input/output
    tool_input = payload.get("tool_input", {})
    tool_output = payload.get("tool_output", "")

    old_string = tool_input.get("old_string", "")
    new_string = tool_input.get("new_string", "")

    if not old_string or not new_string or old_string == new_string:
        return

    # Find brain directory
    brain_dir = os.environ.get("GRADATA_BRAIN_DIR", "")
    if not brain_dir:
        # Try common locations
        for candidate in [Path.cwd() / ".brain", Path.home() / ".gradata"]:
            if candidate.is_dir():
                brain_dir = str(candidate)
                break

    if not brain_dir:
        return  # No brain configured

    try:
        from gradata import Brain
        brain = Brain(brain_dir)
        brain.correct(draft=old_string, final=new_string, category="CODE")
        _log.debug("Captured correction from Claude Code hook")
    except Exception as e:
        _log.debug("Hook capture failed: %s", e)


# ---------------------------------------------------------------------------
# Settings I/O
# ---------------------------------------------------------------------------

def _load_settings() -> dict:
    if _SETTINGS_PATH.is_file():
        return json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
    return {}


def _save_settings(settings: dict) -> None:
    _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SETTINGS_PATH.write_text(
        json.dumps(settings, indent=2) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# CLI entry point (called by Claude Code hook)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if "--capture" in sys.argv:
        capture_correction()
