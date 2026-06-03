from __future__ import annotations

from pathlib import Path

from gradata.hooks.adapters._base import (
    EDIT_TOOL_ALIASES,
    WRITE_TOOL_ALIASES,
    InstallResult,
    _normalize_tool_name,
    auto_correct_command,
    extract_from_edit_args,
    extract_from_write_args,
    failure,
    hook_command,
    hook_signature,
    read_json,
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


def install(brain_dir: Path, agent_config_path: Path) -> InstallResult:
    try:
        sig = hook_signature(AGENT, brain_dir)
        data = read_json(agent_config_path)
        hooks = data.setdefault("hooks", {})

        # PreToolUse: inject_brain_rules
        pre_tool = hooks.setdefault("PreToolUse", [])
        pre_present = any(sig in str(item) for item in pre_tool)
        if not pre_present:
            pre_tool.append(
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": hook_command(brain_dir),
                            "id": sig,
                        }
                    ],
                }
            )

        # PostToolUse: auto_correct (Edit|Write capture)
        post_tool = hooks.setdefault("PostToolUse", [])
        post_present = any(sig in str(item) for item in post_tool)
        if not post_present:
            post_tool.append(
                {
                    "matcher": "Edit|Write",
                    "hooks": [
                        {
                            "type": "command",
                            "command": auto_correct_command(brain_dir),
                            "id": sig,
                        }
                    ],
                }
            )

        write_json(agent_config_path, data)
        added = (0 if pre_present else 1) + (0 if post_present else 1)
        if added == 0:
            return InstallResult(
                AGENT, agent_config_path, "already_present", "both hooks already present"
            )
        return InstallResult(AGENT, agent_config_path, "added", f"installed {added} hook(s)")
    except Exception as exc:
        return failure(AGENT, agent_config_path, exc)


def uninstall(brain_dir: Path, agent_config_path: Path) -> InstallResult:
    """Reverse install(): drop signature-matching PreToolUse + PostToolUse entries.

    Idempotent -- calling on an already-clean config returns already_present
    (semantically: 'already in the desired absent state'). Empty containers
    are pruned. User-owned entries (without our signature) are preserved.
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
            return InstallResult(AGENT, agent_config_path, "already_present", "no hooks block")

        total_removed = 0
        for event_key in ("PreToolUse", "PostToolUse"):
            entries = hooks.get(event_key)
            if not isinstance(entries, list):
                continue

            kept: list = []
            for entry in entries:
                if sig in str(entry):
                    total_removed += 1
                    continue
                kept.append(entry)

            if kept:
                hooks[event_key] = kept
            else:
                hooks.pop(event_key, None)

        if total_removed == 0:
            return InstallResult(AGENT, agent_config_path, "already_present", "hook not present")

        if not hooks:
            data.pop("hooks", None)
        write_json(agent_config_path, data)
        return InstallResult(
            AGENT, agent_config_path, "removed", f"removed {total_removed} hook entry"
        )
    except Exception as exc:
        return failure(AGENT, agent_config_path, exc)
