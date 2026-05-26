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
    pre_compact_hook_command,
    read_json,
    write_json,
)

AGENT = "claude-code"
PRE_COMPACT_ID_SUFFIX = ":precompact"

# Claude Code's canonical tool names (capitalised, no prefix).
EDIT_TOOLS: frozenset[str] = frozenset({"Edit", "MultiEdit"}) | (EDIT_TOOL_ALIASES & {"Edit"})
WRITE_TOOLS: frozenset[str] = frozenset({"Write"}) | (WRITE_TOOL_ALIASES & {"Write"})


def _pre_compact_signature(brain_dir: Path) -> str:
    return f"{hook_signature(AGENT, brain_dir)}{PRE_COMPACT_ID_SUFFIX}"


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
        pre_compact_sig = _pre_compact_signature(brain_dir)
        data = read_json(agent_config_path)
        hooks = data.setdefault("hooks", {})

        added = 0
        pre_tool = hooks.setdefault("PreToolUse", [])
        if not any(sig in str(item) for item in pre_tool):
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
            added += 1

        pre_compact = hooks.setdefault("PreCompact", [])
        if not any(pre_compact_sig in str(item) for item in pre_compact):
            pre_compact.append(
                {
                    "matcher": "manual|auto",
                    "hooks": [
                        {
                            "type": "command",
                            "command": pre_compact_hook_command(brain_dir),
                            "id": pre_compact_sig,
                        }
                    ],
                }
            )
            added += 1

        if added == 0:
            return InstallResult(
                AGENT, agent_config_path, "already_present", "hook already present"
            )
        write_json(agent_config_path, data)
        return InstallResult(AGENT, agent_config_path, "added", "installed PreToolUse and PreCompact hooks")
    except Exception as exc:
        return failure(AGENT, agent_config_path, exc)


def uninstall(brain_dir: Path, agent_config_path: Path) -> InstallResult:
    """Reverse ``install()``: drop signature-matching hook entries.

    Idempotent — calling on an already-clean config returns ``already_present``
    (semantically: 'already in the desired absent state'). Empty containers
    are pruned. User-owned PreToolUse entries (without our signature) are
    preserved verbatim.
    """
    try:
        if not agent_config_path.is_file():
            return InstallResult(
                AGENT, agent_config_path, "already_present", "config file does not exist"
            )
        sig = hook_signature(AGENT, brain_dir)
        pre_compact_sig = _pre_compact_signature(brain_dir)
        data = read_json(agent_config_path)
        hooks = data.get("hooks")
        if not isinstance(hooks, dict):
            return InstallResult(AGENT, agent_config_path, "already_present", "no hooks block")
        removed = 0

        pre_tool = hooks.get("PreToolUse")
        if isinstance(pre_tool, list):
            kept: list = []
            for entry in pre_tool:
                entry_str = str(entry)
                if sig in entry_str and pre_compact_sig not in entry_str:
                    # Either the entry's `hooks[].id` carries our sig, or the
                    # whole entry was ours. Drop it.
                    removed += 1
                    continue
                kept.append(entry)
            if kept:
                hooks["PreToolUse"] = kept
            else:
                hooks.pop("PreToolUse", None)

        pre_compact = hooks.get("PreCompact")
        if isinstance(pre_compact, list):
            kept = []
            for entry in pre_compact:
                if pre_compact_sig in str(entry):
                    removed += 1
                    continue
                kept.append(entry)
            if kept:
                hooks["PreCompact"] = kept
            else:
                hooks.pop("PreCompact", None)

        if removed == 0:
            return InstallResult(AGENT, agent_config_path, "already_present", "hook not present")
        if not hooks:
            data.pop("hooks", None)
        write_json(agent_config_path, data)
        return InstallResult(AGENT, agent_config_path, "removed", f"removed {removed} hook entry")
    except Exception as exc:
        return failure(AGENT, agent_config_path, exc)
