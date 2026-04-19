"""Hook installer -- generates, installs, and manages Claude Code hooks.

This is NOT the brain marketplace installer (src/gradata/_installer.py).
This module manages Claude Code hook registration in ~/.claude/settings.json,
controlling which Gradata hooks activate at each profile tier.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

_log = logging.getLogger(__name__)

from ._base import Profile

# ---------------------------------------------------------------------------
# Hook registry: (module, event, matcher, profile, timeout, description)
# ---------------------------------------------------------------------------

HOOK_REGISTRY: list[tuple[str, str, str | None, Profile, int, str]] = [
    ("auto_correct",         "PostToolUse",      "Edit|Write",           Profile.MINIMAL,  5000,  "Gradata: capture corrections from edits"),
    ("inject_brain_rules",   "SessionStart",     None,                   Profile.MINIMAL,  10000, "Gradata: inject graduated rules at session start"),
    ("session_close",        "Stop",             None,                   Profile.MINIMAL,  15000, "Gradata: emit SESSION_END + run graduation sweep"),
    ("secret_scan",          "PreToolUse",       "Write|Edit|MultiEdit", Profile.STANDARD, 5000,  "Gradata: block secrets in written content"),
    ("config_protection",    "PreToolUse",       "Write|Edit|MultiEdit", Profile.STANDARD, 3000,  "Gradata: block linter config weakening"),
    ("rule_enforcement",     "PreToolUse",       "Write|Edit|MultiEdit", Profile.STANDARD, 5000,  "Gradata: inject RULE reminders before edits"),
    ("generated_runner",     "PreToolUse",       "Write|Edit|MultiEdit|Bash", Profile.STANDARD, 10000, "Gradata: run user-installed generated hooks from gradata rule add"),
    ("generated_runner_post","PostToolUse",      "Write|Edit|MultiEdit",      Profile.STANDARD, 35000, "Gradata: run user-installed post-tool hooks (e.g. auto_test)"),
    ("agent_precontext",     "PreToolUse",       "Agent",                Profile.STANDARD, 8000,  "Gradata: inject rules into sub-agent prompts"),
    ("agent_graduation",     "PostToolUse",      "Agent",                Profile.STANDARD, 10000, "Gradata: record agent outcomes for graduation"),
    ("tool_failure_emit",    "PostToolUse",      "Bash",                 Profile.STANDARD, 5000,  "Gradata: track tool failures with backoff"),
    ("tool_finding_capture", "PostToolUse",      "Bash|Edit|Write",      Profile.STANDARD, 5000,  "Gradata: bridge lint/test findings to corrections"),
    ("config_validate",      "SessionStart",     None,                   Profile.STANDARD, 5000,  "Gradata: validate settings.json integrity"),
    ("context_inject",       "UserPromptSubmit", None,                   Profile.STANDARD, 8000,  "Gradata: inject brain context on user message"),
    ("pre_compact",          "PreCompact",       "manual|auto",          Profile.STANDARD, 5000,  "Gradata: save state before context compression"),
    ("duplicate_guard",      "PreToolUse",       "Write",                Profile.STRICT,   3000,  "Gradata: block new files when similar exists"),
    ("brain_maintain",       "Stop",             None,                   Profile.STRICT,   20000, "Gradata: FTS rebuild + brain maintenance"),
    ("session_persist",      "Stop",             None,                   Profile.STRICT,   10000, "Gradata: crash-safe session handoff"),
    ("implicit_feedback",    "UserPromptSubmit", None,                   Profile.STRICT,   5000,  "Gradata: detect pushback as implicit corrections"),
    ("stale_hook_check",     "SessionStart",     None,                   Profile.STANDARD, 5000,  "Gradata: warn on stale generated hooks at session start"),
]

SETTINGS_PATH = Path.home() / ".claude" / "settings.json"


# ---------------------------------------------------------------------------
# Generate settings dict
# ---------------------------------------------------------------------------

def generate_settings(profile: str = "standard") -> dict:
    """Generate a Claude Code settings dict with hooks for the given profile."""
    mapping = {"minimal": Profile.MINIMAL, "standard": Profile.STANDARD, "strict": Profile.STRICT}
    max_profile = mapping.get(profile.lower().strip(), Profile.STANDARD)

    hooks_by_event: dict[str, list[dict]] = {}

    for module, event, matcher, min_profile, timeout, description in HOOK_REGISTRY:
        if min_profile > max_profile:
            continue

        hook_entry = {
            "type": "command",
            "command": f"{sys.executable} -m gradata.hooks.{module}",
            "timeout": timeout,
        }

        if event not in hooks_by_event:
            hooks_by_event[event] = []

        group = {
            "hooks": [hook_entry],
            "description": description,
        }
        if matcher:
            group["matcher"] = matcher

        hooks_by_event[event].append(group)

    return {"hooks": hooks_by_event}


# ---------------------------------------------------------------------------
# Settings I/O
# ---------------------------------------------------------------------------

def _load_settings() -> dict:
    if SETTINGS_PATH.is_file():
        try:
            return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            _log.warning("Corrupted settings.json at %s — starting fresh", SETTINGS_PATH)
            return {}
    return {}


def _save_settings(settings: dict) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(
        json.dumps(settings, indent=2) + "\n", encoding="utf-8"
    )


def _is_gradata_hook(hook_group: dict) -> bool:
    """Check if a hook group belongs to Gradata."""
    desc = hook_group.get("description", "")
    if "Gradata:" in desc or "gradata" in desc.lower():
        return True
    for hook in hook_group.get("hooks", []):
        cmd = hook.get("command", "")
        if "gradata.hooks." in cmd:
            return True
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def install(profile: str = "standard") -> None:
    """Install Gradata hooks into ~/.claude/settings.json."""
    settings = _load_settings()

    # Remove any existing Gradata hooks first
    uninstall_from(settings)

    # Generate new hooks
    new = generate_settings(profile)

    existing_hooks = settings.setdefault("hooks", {})
    for event, groups in new["hooks"].items():
        if event not in existing_hooks:
            existing_hooks[event] = []
        existing_hooks[event].extend(groups)

    _save_settings(settings)

    count = sum(len(groups) for groups in new["hooks"].values())
    _log.info("Gradata hooks installed (%d hooks, profile=%s)", count, profile)
    _log.info("  Settings: %s", SETTINGS_PATH)

    # Activation telemetry — fires once per machine, only if opted in.
    try:
        from .. import _telemetry

        _telemetry.send_once("first_hook_installed")
    except Exception:
        pass


def uninstall() -> None:
    """Remove all Gradata hooks from ~/.claude/settings.json."""
    settings = _load_settings()
    removed = uninstall_from(settings)
    _save_settings(settings)
    if removed:
        _log.info("Removed %d Gradata hook(s).", removed)
    else:
        _log.info("No Gradata hooks found.")


def uninstall_from(settings: dict) -> int:
    """Remove Gradata hooks from a settings dict. Returns count removed."""
    hooks = settings.get("hooks", {})
    removed = 0
    for event in list(hooks.keys()):
        original = hooks[event]
        filtered = [g for g in original if not _is_gradata_hook(g)]
        removed += len(original) - len(filtered)
        if filtered:
            hooks[event] = filtered
        else:
            del hooks[event]
    return removed


def status() -> None:
    """Show installed Gradata hooks."""
    settings = _load_settings()
    hooks = settings.get("hooks", {})

    gradata_hooks = []
    for event, groups in hooks.items():
        for group in groups:
            if _is_gradata_hook(group):
                desc = group.get("description", "?")
                for hook in group.get("hooks", []):
                    gradata_hooks.append({
                        "event": event,
                        "command": hook.get("command", "?"),
                        "description": desc,
                        "timeout": hook.get("timeout", "?"),
                    })

    if gradata_hooks:
        _log.info("Gradata hooks: %d INSTALLED", len(gradata_hooks))
        _log.info("  Settings: %s", SETTINGS_PATH)
        for h in gradata_hooks:
            _log.info("  [%s] %s", h["event"], h["description"])
    else:
        _log.info("Gradata hooks: NOT INSTALLED")
        _log.info("  Run: gradata hooks install")
