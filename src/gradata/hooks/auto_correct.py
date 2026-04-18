#!/usr/bin/env python3
"""
Auto-Correct Hook — Automatic correction capture for Claude Code.
===================================================================
PostToolUse hook that fires on Edit/Write tool calls and captures
the before/after diff as a brain correction. Install once, learn forever.

This is the "install and forget" piece. Without this hook, users have
to manually call brain_correct(). With it, every edit the user makes
(or accepts) is automatically captured as a learning signal.

Installation (Claude Code settings.json):
    {
      "hooks": {
        "PostToolUse": [{
          "matcher": "Edit|Write",
          "command": "python -m gradata.hooks.auto_correct"
        }]
      }
    }

The hook reads tool input/output from stdin (JSON), extracts the
before/after content, and calls brain.correct() if a meaningful
diff exists.

Also works as a standalone CLI for testing:
    echo '{"tool_name":"Edit","input":{"old_string":"Dear","new_string":"Hey"}}' | python -m gradata.hooks.auto_correct
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ._base import run_hook
from ._profiles import Profile

HOOK_META = {
    "event": "PostToolUse",
    "matcher": "Edit|Write",
    "profile": Profile.MINIMAL,
    "timeout": 5000,
}


def _get_brain():
    """Get or auto-initialize a brain instance."""
    try:
        from ..brain import Brain
    except ImportError:
        return None

    brain_dir = os.environ.get("BRAIN_DIR", str(Path.home() / ".gradata" / "brain"))
    brain_path = Path(brain_dir)

    try:
        if brain_path.exists():
            return Brain(brain_dir)
        else:
            return Brain.init(brain_dir, domain="General")
    except Exception:
        return None


def _extract_correction(tool_input: dict, tool_output: dict | str | None = None) -> tuple[str, str] | None:
    """Extract before/after text from a tool call.

    Handles Edit (old_string/new_string) and Write (checks git diff).
    Returns (draft, final) or None if no meaningful correction.
    """
    tool_name = tool_input.get("tool_name", "")

    if tool_name == "Edit":
        old = tool_input.get("input", {}).get("old_string", "")
        new = tool_input.get("input", {}).get("new_string", "")
        if old and new and old != new:
            return (old, new)

    elif tool_name == "Write":
        # For Write, we need the previous file content
        # The hook receives the tool output which may include the old content
        new_content = tool_input.get("input", {}).get("content", "")

        if isinstance(tool_output, dict) and tool_output.get("old_content"):
            old_content = tool_output["old_content"]
            if old_content != new_content and old_content and new_content:
                return (old_content[:5000], new_content[:5000])

    return None


def process_hook_input(raw_input: str) -> dict:
    """Process hook stdin and return result.

    Args:
        raw_input: JSON string from Claude Code hook system.

    Returns:
        Dict with 'captured' bool and optional 'severity'.
    """
    try:
        data = json.loads(raw_input)
    except json.JSONDecodeError:
        return {"captured": False, "reason": "invalid_json"}

    correction = _extract_correction(data, data.get("tool_output"))
    if correction is None:
        return {"captured": False, "reason": "no_correction"}

    draft, final = correction
    brain = _get_brain()
    if brain is None:
        return {"captured": False, "reason": "brain_unavailable"}

    try:
        event = brain.correct(draft, final)
        severity = event.get("data", {}).get("severity", "unknown")

        # Build human-friendly progress message
        progress = _build_progress(brain, event)

        result = {
            "captured": True,
            "severity": severity,
            "edit_distance": event.get("data", {}).get("edit_distance", 0),
        }
        if progress:
            result["result"] = progress  # Claude Code displays "result" to the user
        return result
    except (ValueError, Exception) as e:
        return {"captured": False, "reason": str(e)}


def _build_progress(brain, event: dict) -> str:
    """Build a plain-English progress message after a correction.

    No jargon. No decimals. Just: how close is this to becoming a rule?
    """
    try:
        from ..enhancements.self_improvement import parse_lessons
    except ImportError:
        return ""

    lessons_path = brain._find_lessons_path()
    if not lessons_path or not lessons_path.is_file():
        return ""

    try:
        text = lessons_path.read_text(encoding="utf-8")
        lessons = parse_lessons(text)
    except Exception:
        return ""

    if not lessons:
        return ""

    # Find the most relevant lesson (most recently modified or matching category)
    category = event.get("data", {}).get("category", "")
    matching = [lesson for lesson in lessons if lesson.category == category] if category else []
    lesson = matching[-1] if matching else lessons[-1]

    confidence = lesson.confidence
    description = lesson.description

    # Trim description to something readable
    if len(description) > 60:
        description = description[:57] + "..."

    # Calculate progress as "X of 5 corrections"
    # PATTERN at 0.60, RULE at 0.90. Each correction adds ~0.07-0.10
    # Approximate: 5 reinforcing corrections to go from 0.40 to 0.90
    total_rules = sum(1 for l in lessons if l.confidence >= 0.60)

    if confidence >= 0.90:
        return f"Learned. {total_rules} rules active."
    elif confidence >= 0.60:
        steps_left = max(1, round((0.90 - confidence) / 0.08))
        return f"Learned. {steps_left} more to lock in. {total_rules} rules active."
    else:
        steps_left = max(1, round((0.60 - confidence) / 0.08))
        return f"Noted. {steps_left} more corrections to activate."


def generate_hook_config(brain_dir: str | None = None) -> dict:
    """Generate Claude Code settings.json hook configuration.

    Returns the hooks section that should be merged into the user's
    settings.json to enable automatic correction capture.

    Args:
        brain_dir: Optional brain directory. Defaults to ~/.gradata/brain.
    """
    brain_dir = brain_dir or str(Path.home() / ".gradata" / "brain")

    return {
        "hooks": {
            "PostToolUse": [
                {
                    "matcher": "Edit",
                    "command": "python -m gradata.hooks.auto_correct",
                    "description": "Gradata: capture corrections from edits",
                },
                {
                    "matcher": "Write",
                    "command": "python -m gradata.hooks.auto_correct",
                    "description": "Gradata: capture corrections from file writes",
                },
            ],
        },
    }


def generate_mcp_config(brain_dir: str | None = None) -> dict:
    """Generate Claude Code MCP server configuration.

    Returns the mcpServers section for the user's settings.json.
    """
    brain_dir = brain_dir or str(Path.home() / ".gradata" / "brain")

    return {
        "mcpServers": {
            "gradata": {
                "command": "python",
                "args": ["-m", "gradata.mcp_server", "--brain-dir", brain_dir],
            },
        },
    }


def generate_full_config(brain_dir: str | None = None) -> dict:
    """Generate complete Claude Code configuration for Gradata.

    Combines MCP server + auto-correct hook into one config block.
    """
    hook_config = generate_hook_config(brain_dir)
    mcp_config = generate_mcp_config(brain_dir)
    return {**mcp_config, **hook_config}


def main(data: dict) -> dict | None:
    """Hook entry point: receive parsed data from run_hook, process, return result."""
    if not data:
        return None

    tool_output = data.get("tool_output") or data.get("output")
    correction = _extract_correction(data, tool_output)
    if correction is None:
        return None

    draft, final = correction
    brain = _get_brain()
    if brain is None:
        return None

    try:
        event = brain.correct(draft, final)
        severity = event.get("data", {}).get("severity", "unknown")
        progress = _build_progress(brain, event)
        result = {
            "captured": True,
            "severity": severity,
            "edit_distance": event.get("data", {}).get("edit_distance", 0),
        }
        if progress:
            result["result"] = progress
        return result
    except Exception:
        return None


if __name__ == "__main__":
    run_hook(main, HOOK_META)
