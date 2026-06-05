from __future__ import annotations

from pathlib import Path

from gradata.hooks.adapters._base import (
    EDIT_TOOL_ALIASES,
    WRITE_TOOL_ALIASES,
    InstallResult,
    _normalize_tool_name,
    extract_from_edit_args,
    extract_from_write_args,
    failure,
    hook_command,
    hook_signature,
    post_tool_hook_command,
    read_json,
    session_end_hook_command,
    write_json,
)

AGENT = "claude-code"

# Claude Code's canonical tool names (capitalised, no prefix).
EDIT_TOOLS: frozenset[str] = frozenset({"Edit", "MultiEdit"}) | (EDIT_TOOL_ALIASES & {"Edit"})
WRITE_TOOLS: frozenset[str] = frozenset({"Write"}) | (WRITE_TOOL_ALIASES & {"Write"})


def detect(payload: dict) -> bool:
    """Claude Code stdin signature: capitalised tool name + args at ``input``.

    The Claude Code hook protocol pipes JSON with ``{"tool_name": "Edit",
    "input": {...}}``. The capitalised tool name and the ``input`` key
    (not ``tool_input``) are the disambiguating features.
    """
    if not isinstance(payload, dict):
        return False
    tool_name = _normalize_tool_name(payload.get("tool_name") or "")
    return tool_name in EDIT_TOOLS or tool_name in WRITE_TOOLS


def extract_correction(
    payload: dict, tool_output: dict | str | None = None
) -> tuple[str, str] | None:
    """Extract (draft, final) from a Claude Code post-tool-use payload."""
    tool_name = _normalize_tool_name(payload.get("tool_name") or "")
    args = payload.get("input")
    if not isinstance(args, dict):
        return None

    if tool_name in EDIT_TOOLS:
        return extract_from_edit_args(args)
    if tool_name in WRITE_TOOLS:
        return extract_from_write_args(args, tool_output)
    return None


# Canonical hook entries for the MINIMAL profile.
# (event, matcher, command_fn, description)
_HOOK_ENTRIES = [
    ("PreToolUse", "*", hook_command, "Gradata: inject graduated rules at session start"),
    ("PostToolUse", "Edit|Write", post_tool_hook_command, "Gradata: capture corrections from edits"),
    ("Stop", None, session_end_hook_command, "Gradata: emit SESSION_END + run graduation sweep"),
]


def _entry_has_hook_id(entry: object, hook_id: str) -> bool:
    if not isinstance(entry, dict):
        return False
    hooks = entry.get("hooks")
    if not isinstance(hooks, list):
        return False
    return any(isinstance(hook, dict) and hook.get("id") == hook_id for hook in hooks)


def install(brain_dir: Path, agent_config_path: Path) -> InstallResult:
    """Install/repair the MINIMAL hook set: PreToolUse (inject), PostToolUse
    (auto_correct), and Stop (session_close).

    Idempotent per event -- existing signed entries are preserved, while missing
    signed entries are added so partially deleted installs self-heal.
    """
    try:
        sig = hook_signature(AGENT, brain_dir)
        data = read_json(agent_config_path)
        hooks = data.setdefault("hooks", {})

        added: list[str] = []
        for event, matcher, cmd_fn, _desc in _HOOK_ENTRIES:
            entries = hooks.setdefault(event, [])
            if not isinstance(entries, list):
                entries = []
                hooks[event] = entries
            if any(_entry_has_hook_id(existing, sig) for existing in entries):
                continue
            entry = {
                "hooks": [
                    {
                        "type": "command",
                        "command": cmd_fn(brain_dir),
                        "id": sig,
                    }
                ],
            }
            if matcher:
                entry["matcher"] = matcher
            entries.append(entry)
            added.append(event)

        if not added:
            return InstallResult(
                AGENT, agent_config_path, "already_present", "hooks already present"
            )
        write_json(agent_config_path, data)
        return InstallResult(
            AGENT,
            agent_config_path,
            "added",
            f"installed {' + '.join(added)} hooks",
        )
    except Exception as exc:
        return failure(AGENT, agent_config_path, exc)


def uninstall(brain_dir: Path, agent_config_path: Path) -> InstallResult:
    """Reverse ``install()``: drop signature-matching entries from ALL
    hook events.

    Idempotent -- calling on an already-clean config returns
    ``already_present`` (semantically: 'already in the desired absent
    state'). Empty containers are pruned. User-owned entries (without
    our signature) are preserved.
    """
    try:
        if not agent_config_path.is_file():
            return InstallResult(
                AGENT, agent_config_path, "already_present", "config file does not exist"
            )
        sig = hook_signature(AGENT, brain_dir)
        data = read_json(agent_config_path)
        hooks = data.get("hooks")
        if not isinstance(hooks, dict):
            return InstallResult(
                AGENT, agent_config_path, "already_present", "no hooks block"
            )

        total_removed = 0
        for event, _matcher, _cmd_fn, _desc in _HOOK_ENTRIES:
            entries = hooks.get(event)
            if not isinstance(entries, list):
                continue
            removed = 0
            kept: list = []
            for entry in entries:
                if _entry_has_hook_id(entry, sig):
                    removed += 1
                    continue
                kept.append(entry)
            if removed > 0:
                total_removed += removed
                if kept:
                    hooks[event] = kept
                else:
                    hooks.pop(event, None)

        if total_removed == 0:
            return InstallResult(AGENT, agent_config_path, "already_present", "hook not present")

        if not hooks:
            data.pop("hooks", None)
        write_json(agent_config_path, data)
        return InstallResult(
            AGENT, agent_config_path, "removed", f"removed {total_removed} hook entries"
        )
    except Exception as exc:
        return failure(AGENT, agent_config_path, exc)
