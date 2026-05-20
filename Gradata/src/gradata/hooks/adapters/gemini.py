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

AGENT = "gemini"

# Gemini CLI surfaces tools via the Gemini SDK; canonical tool names use
# CamelCase or lowercase depending on version. The shared allowlists cover
# both shapes.
GEMINI_EDIT_TOOLS = EDIT_TOOL_ALIASES
GEMINI_WRITE_TOOLS = WRITE_TOOL_ALIASES


def detect(payload: dict) -> bool:
    """Gemini stdin: ``{"tool": "...", "args": {...}}``.

    Distinct from Claude Code (``input`` not ``args``) and Hermes
    (``hook_event_name`` envelope absent).
    """
    if not isinstance(payload, dict):
        return False
    if "args" not in payload or "hook_event_name" in payload:
        return False
    tool_name = _normalize_tool_name(payload.get("tool") or payload.get("tool_name") or "")
    return tool_name in GEMINI_EDIT_TOOLS or tool_name in GEMINI_WRITE_TOOLS


def extract_correction(
    payload: dict, tool_output: dict | str | None = None
) -> tuple[str, str] | None:
    tool_name = _normalize_tool_name(payload.get("tool") or payload.get("tool_name") or "")
    args = payload.get("args")
    if not isinstance(args, dict):
        return None

    if tool_name in GEMINI_EDIT_TOOLS:
        return extract_from_edit_args(args)
    if tool_name in GEMINI_WRITE_TOOLS:
        return extract_from_write_args(args, tool_output)
    return None


def install(brain_dir: Path, agent_config_path: Path) -> InstallResult:
    try:
        sig = hook_signature(AGENT, brain_dir)
        data = read_json(agent_config_path)
        tools = data.setdefault("tools", {})
        pre_call = tools.setdefault("preCall", [])
        if any(sig in str(item) for item in pre_call):
            return InstallResult(
                AGENT, agent_config_path, "already_present", "hook already present"
            )
        pre_call.append({"id": sig, "command": hook_command(brain_dir)})
        write_json(agent_config_path, data)
        return InstallResult(AGENT, agent_config_path, "added", "installed tools.preCall hook")
    except Exception as exc:
        return failure(AGENT, agent_config_path, exc)


def uninstall(brain_dir: Path, agent_config_path: Path) -> InstallResult:
    """Reverse install: drop signature-matching entries from tools.preCall."""
    from gradata.hooks.adapters._base import uninstall_from_list_in_dict

    return uninstall_from_list_in_dict(
        agent=AGENT,
        brain_dir=brain_dir,
        agent_config_path=agent_config_path,
        outer_key="tools",
        inner_key="preCall",
    )
