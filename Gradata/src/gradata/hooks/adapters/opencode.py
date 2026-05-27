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

AGENT = "opencode"

OPENCODE_EDIT_TOOLS = EDIT_TOOL_ALIASES
OPENCODE_WRITE_TOOLS = WRITE_TOOL_ALIASES


def detect(payload: dict) -> bool:
    """OpenCode stdin: ``{"event": "preTool", "tool": "...", "input": {...}}``."""
    if not isinstance(payload, dict):
        return False
    return payload.get("event") in {"preTool", "postTool"}


def extract_correction(
    payload: dict, tool_output: dict | str | None = None
) -> tuple[str, str] | None:
    tool_name = _normalize_tool_name(payload.get("tool") or payload.get("tool_name") or "")
    args = payload.get("input")
    if not isinstance(args, dict):
        return None

    if tool_name in OPENCODE_EDIT_TOOLS:
        return extract_from_edit_args(args)
    if tool_name in OPENCODE_WRITE_TOOLS:
        return extract_from_write_args(args, tool_output)
    return None


def install(brain_dir: Path, agent_config_path: Path) -> InstallResult:
    try:
        sig = hook_signature(AGENT, brain_dir)
        data = read_json(agent_config_path)
        hooks = data.setdefault("hooks", {})
        added: list[str] = []
        for key, command in (
            ("preTool", hook_command(brain_dir)),
            ("postTool", post_tool_hook_command(brain_dir)),
            ("sessionEnd", session_end_hook_command(brain_dir)),
        ):
            entries = hooks.setdefault(key, [])
            if not isinstance(entries, list):
                entries = []
                hooks[key] = entries
            if any(sig in str(item) for item in entries):
                continue
            entries.append({"id": sig, "command": command})
            added.append(key)
        if not added:
            return InstallResult(
                AGENT, agent_config_path, "already_present", "hooks already present"
            )
        write_json(agent_config_path, data)
        return InstallResult(
            AGENT,
            agent_config_path,
            "added",
            "installed preTool, postTool, and sessionEnd hooks",
        )
    except Exception as exc:
        return failure(AGENT, agent_config_path, exc)


def uninstall(brain_dir: Path, agent_config_path: Path) -> InstallResult:
    """Reverse install: drop signature-matching entries from OpenCode hooks."""
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

        removed = 0
        for key in ("preTool", "postTool", "sessionEnd"):
            entries = hooks.get(key)
            if not isinstance(entries, list):
                continue
            kept = []
            for entry in entries:
                if sig in str(entry):
                    removed += 1
                    continue
                kept.append(entry)
            if kept:
                hooks[key] = kept
            else:
                hooks.pop(key, None)

        if removed == 0:
            return InstallResult(AGENT, agent_config_path, "already_present", "hook not present")

        if not hooks:
            data.pop("hooks", None)
        write_json(agent_config_path, data)
        return InstallResult(AGENT, agent_config_path, "removed", f"removed {removed} hook entry")
    except Exception as exc:
        return failure(AGENT, agent_config_path, exc)
