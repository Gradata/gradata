"""Hook installer -- generates, installs, and manages Claude Code hooks.

This is NOT the brain marketplace installer (src/gradata/_installer.py).
This module manages Claude Code hook registration in ~/.claude/settings.json,
controlling which Gradata hooks activate at each profile tier.
"""

from __future__ import annotations

import json
import logging
import stat
import sys
from pathlib import Path

_log = logging.getLogger(__name__)

from gradata.hooks._profiles import Profile

# ---------------------------------------------------------------------------
# Hook registry: (module, event, matcher, profile, timeout, description)
# ---------------------------------------------------------------------------

HOOK_REGISTRY: list[tuple[str, str, str | None, Profile, int, str]] = [
    (
        "auto_correct",
        "PostToolUse",
        "Edit|Write",
        Profile.MINIMAL,
        5000,
        "Gradata: capture corrections from edits",
    ),
    (
        "inject_brain_rules",
        "SessionStart",
        None,
        Profile.MINIMAL,
        10000,
        "Gradata: inject graduated rules at session start",
    ),
    (
        "session_close",
        "Stop",
        None,
        Profile.MINIMAL,
        15000,
        "Gradata: emit SESSION_END + run graduation sweep",
    ),
    (
        "secret_scan",
        "PreToolUse",
        "Write|Edit|MultiEdit",
        Profile.STANDARD,
        5000,
        "Gradata: block secrets in written content",
    ),
    (
        "config_protection",
        "PreToolUse",
        "Write|Edit|MultiEdit",
        Profile.STANDARD,
        3000,
        "Gradata: block linter config weakening",
    ),
    (
        "rule_enforcement",
        "PreToolUse",
        "Write|Edit|MultiEdit",
        Profile.STANDARD,
        5000,
        "Gradata: inject RULE reminders before edits",
    ),
    (
        "generated_runner",
        "PreToolUse",
        "Write|Edit|MultiEdit|Bash",
        Profile.STANDARD,
        10000,
        "Gradata: run user-installed generated hooks from gradata rule add",
    ),
    (
        "generated_runner_post",
        "PostToolUse",
        "Write|Edit|MultiEdit",
        Profile.STANDARD,
        35000,
        "Gradata: run user-installed post-tool hooks (e.g. auto_test)",
    ),
    (
        "agent_precontext",
        "PreToolUse",
        "Agent",
        Profile.STANDARD,
        8000,
        "Gradata: inject rules into sub-agent prompts",
    ),
    (
        "agent_graduation",
        "PostToolUse",
        "Agent",
        Profile.STANDARD,
        10000,
        "Gradata: record agent outcomes for graduation",
    ),
    (
        "tool_failure_emit",
        "PostToolUse",
        "Bash",
        Profile.STANDARD,
        5000,
        "Gradata: track tool failures with backoff",
    ),
    (
        "tool_finding_capture",
        "PostToolUse",
        "Bash|Edit|Write",
        Profile.STANDARD,
        5000,
        "Gradata: bridge lint/test findings to corrections",
    ),
    (
        "config_validate",
        "SessionStart",
        None,
        Profile.STANDARD,
        5000,
        "Gradata: validate settings.json integrity",
    ),
    (
        "context_inject",
        "UserPromptSubmit",
        None,
        Profile.STANDARD,
        8000,
        "Gradata: inject brain context on user message",
    ),
    (
        "pre_compact",
        "PreCompact",
        "manual|auto",
        Profile.STANDARD,
        5000,
        "Gradata: save state before context compression",
    ),
    (
        "duplicate_guard",
        "PreToolUse",
        "Write",
        Profile.STRICT,
        3000,
        "Gradata: block new files when similar exists",
    ),
    (
        "brain_maintain",
        "Stop",
        None,
        Profile.STRICT,
        20000,
        "Gradata: FTS rebuild + brain maintenance",
    ),
    ("session_persist", "Stop", None, Profile.STRICT, 10000, "Gradata: crash-safe session handoff"),
    (
        "implicit_feedback",
        "UserPromptSubmit",
        None,
        Profile.STRICT,
        5000,
        "Gradata: detect pushback as implicit corrections",
    ),
    (
        "stale_hook_check",
        "SessionStart",
        None,
        Profile.STANDARD,
        5000,
        "Gradata: warn on stale generated hooks at session start",
    ),
]

# ---------------------------------------------------------------------------
# JS asset registry — Claude-Code-specific Node hooks bundled as package data.
# Tuple shape: (asset_subdir, asset_filename, event, matcher, profile, timeout, description)
# These run via `node <project>/.claude/hooks/<subdir>/<filename>` instead of
# `python -m gradata.hooks.<module>`. They wire features (like the handoff
# watchdog from #127) into Claude Code's runtime — features that need access
# to JS-only surfaces such as the statusline bridge file.
# ---------------------------------------------------------------------------

JS_HOOK_REGISTRY: list[tuple[str, str, str, str | None, Profile, int, str]] = [
    (
        "user-prompt",
        "handoff-watchdog.js",
        "UserPromptSubmit",
        None,
        Profile.STANDARD,
        5000,
        "Gradata: handoff watchdog — emit handoff directive on context pressure",
    ),
    (
        "session-start",
        "handoff-inject.js",
        "SessionStart",
        None,
        Profile.STANDARD,
        5000,
        "Gradata: handoff inject — replay previous-session handoff on start",
    ),
]

# Where bundled JS asset sources live inside the installed package
_JS_ASSETS_ROOT = Path(__file__).parent / "assets" / "claude_code"

SETTINGS_PATH = Path.home() / ".claude" / "settings.json"


# ---------------------------------------------------------------------------
# Generate settings dict
# ---------------------------------------------------------------------------


def generate_settings(profile: str = "standard", project_dir: Path | None = None) -> dict:
    """Generate a Claude Code settings dict with hooks for the given profile.

    If ``project_dir`` is supplied, the JS hooks bundled under
    ``assets/claude_code/`` are also registered (referenced via their
    on-disk path under ``<project_dir>/.claude/hooks/``).
    """
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

    # JS asset hooks — only register if a project_dir is supplied, since the
    # `node <path>` command needs an actual on-disk script.
    if project_dir is not None:
        for subdir, filename, event, matcher, min_profile, timeout, description in JS_HOOK_REGISTRY:
            if min_profile > max_profile:
                continue
            script_path = Path(project_dir) / ".claude" / "hooks" / subdir / filename
            hook_entry = {
                "type": "command",
                "command": f"node {script_path}",
                "timeout": timeout,
            }
            hooks_by_event.setdefault(event, []).append(
                {
                    "hooks": [hook_entry],
                    "description": description,
                    **({"matcher": matcher} if matcher else {}),
                }
            )

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
    SETTINGS_PATH.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")


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


def install(
    profile: str = "standard", project_dir: Path | None = None, include_watchdog: bool = False
) -> None:
    """Install Gradata hooks into ~/.claude/settings.json.

    Args:
        profile: Hook profile tier — minimal, standard, or strict.
        project_dir: If supplied, JS asset hooks are copied into
            ``<project_dir>/.claude/hooks/`` (when the directory exists or the
            user opted in) and registered in settings. Required when
            ``include_watchdog`` is True at MINIMAL profile or to override the
            default profile-tier behavior.
        include_watchdog: Force-include the JS handoff watchdog hooks even if
            the chosen profile would not normally activate them. No-op without
            ``project_dir``.
    """
    settings = _load_settings()

    # Remove any existing Gradata hooks first
    uninstall_from(settings)

    # Copy JS asset files when a project_dir is supplied. We always copy when
    # asked — registry filtering controls which entries land in settings.json.
    js_target = None
    if project_dir is not None:
        js_target = install_js_hooks(Path(project_dir))

    # Generate new hooks (settings entries — JS entries only added when
    # project_dir is supplied so the `node <path>` command is real on disk).
    new = generate_settings(
        profile,
        project_dir=Path(project_dir) if project_dir is not None else None,
    )

    # If include_watchdog forces the JS hooks on a profile that would have
    # filtered them out, splice them in explicitly.
    if include_watchdog and project_dir is not None:
        for (
            subdir,
            filename,
            event,
            matcher,
            _min_profile,
            timeout,
            description,
        ) in JS_HOOK_REGISTRY:
            script_path = Path(project_dir) / ".claude" / "hooks" / subdir / filename
            entry = {
                "hooks": [
                    {
                        "type": "command",
                        "command": f"node {script_path}",
                        "timeout": timeout,
                    }
                ],
                "description": description,
            }
            if matcher:
                entry["matcher"] = matcher
            event_groups = new["hooks"].setdefault(event, [])
            # Idempotent: skip if a group with the same description already exists
            if not any(g.get("description") == description for g in event_groups):
                event_groups.append(entry)

    existing_hooks = settings.setdefault("hooks", {})
    for event, groups in new["hooks"].items():
        if event not in existing_hooks:
            existing_hooks[event] = []
        existing_hooks[event].extend(groups)

    _save_settings(settings)

    count = sum(len(groups) for groups in new["hooks"].values())
    _log.info("Gradata hooks installed (%d hooks, profile=%s)", count, profile)
    _log.info("  Settings: %s", SETTINGS_PATH)
    if js_target is not None:
        _log.info("  JS assets: %s", js_target)

    # Activation telemetry — fires once per machine, only if opted in.
    try:
        from gradata import _telemetry

        _telemetry.send_once("first_hook_installed")
    except Exception:
        pass


def install_js_hooks(project_dir: Path) -> Path:
    """Copy bundled JS hook assets into ``<project_dir>/.claude/hooks/``.

    Idempotent: existing files with identical content are left alone; differing
    files are overwritten (the SDK ships the canonical version). Preserves the
    executable bit on Unix-like systems.

    Returns the destination root (``<project_dir>/.claude/hooks/``) so callers
    can log it.
    """
    project_dir = Path(project_dir)
    target_root = project_dir / ".claude" / "hooks"
    target_root.mkdir(parents=True, exist_ok=True)

    if not _JS_ASSETS_ROOT.is_dir():
        _log.warning("JS asset root missing: %s", _JS_ASSETS_ROOT)
        return target_root

    for subdir, filename, *_rest in JS_HOOK_REGISTRY:
        src = _JS_ASSETS_ROOT / subdir / filename
        if not src.is_file():
            _log.warning("JS asset not bundled: %s", src)
            continue
        dst_dir = target_root / subdir
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / filename

        new_bytes = src.read_bytes()
        if dst.is_file() and dst.read_bytes() == new_bytes:
            _log.debug("JS hook unchanged: %s", dst)
            continue

        dst.write_bytes(new_bytes)
        # Preserve executable bit (no-op on Windows)
        try:
            mode = dst.stat().st_mode
            dst.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        except OSError:
            pass
        _log.info("Installed JS hook: %s", dst)

    return target_root


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
                    gradata_hooks.append(
                        {
                            "event": event,
                            "command": hook.get("command", "?"),
                            "description": desc,
                            "timeout": hook.get("timeout", "?"),
                        }
                    )

    if gradata_hooks:
        _log.info("Gradata hooks: %d INSTALLED", len(gradata_hooks))
        _log.info("  Settings: %s", SETTINGS_PATH)
        for h in gradata_hooks:
            _log.info("  [%s] %s", h["event"], h["description"])
    else:
        _log.info("Gradata hooks: NOT INSTALLED")
        _log.info("  Run: gradata hooks install")
