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
    read_json,
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
        pre_tool = hooks.setdefault("preTool", [])
        if any(sig in str(item) for item in pre_tool):
            return InstallResult(
                AGENT, agent_config_path, "already_present", "hook already present"
            )
        pre_tool.append({"id": sig, "command": hook_command(brain_dir)})
        write_json(agent_config_path, data)
        return InstallResult(AGENT, agent_config_path, "added", "installed preTool hook")
    except Exception as exc:
        return failure(AGENT, agent_config_path, exc)
