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
HOOKS: tuple[tuple[str, str], ...] = (
    ("preTool", "inject_brain_rules"),
    ("postTool", "auto_correct"),
    ("sessionEnd", "session_close"),
)

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
        if _has_exact_installed_hook_set(hooks, sig):
            return InstallResult(
                AGENT, agent_config_path, "already_present", "hook already present"
            )
        for event, module in HOOKS:
            _remove_existing_module_hook(hooks, event, module)
            hooks.setdefault(event, []).append(
                {"id": f"{sig}:{event}:{module}", "command": hook_command(brain_dir, module)}
            )
        write_json(agent_config_path, data)
        return InstallResult(AGENT, agent_config_path, "added", "installed OpenCode hooks")
    except Exception as exc:
        return failure(AGENT, agent_config_path, exc)


def _is_gradata_module_hook(item: object, event: str, module: str) -> bool:
    text = str(item)
    return f"gradata.hooks.{module}" in text or (
        f"gradata:{AGENT}:" in text and f":{event}:{module}" in text
    )


def _has_exact_installed_hook_set(hooks: dict, sig: str) -> bool:
    for event, module in HOOKS:
        entries = hooks.get(event)
        if not isinstance(entries, list):
            return False
        module_entries = [entry for entry in entries if _is_gradata_module_hook(entry, event, module)]
        if len(module_entries) != 1:
            return False
        if f"{sig}:{event}:{module}" not in str(module_entries[0]):
            return False
    return True


def _remove_existing_module_hook(hooks: dict, event: str, module: str) -> None:
    entries = hooks.get(event)
    if not isinstance(entries, list):
        return
    kept = [entry for entry in entries if not _is_gradata_module_hook(entry, event, module)]
    if kept:
        hooks[event] = kept
    else:
        hooks.pop(event, None)


def uninstall(brain_dir: Path, agent_config_path: Path) -> InstallResult:
    """Reverse install: drop signature-matching entries from all OpenCode hooks."""
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
        for event in list(hooks):
            entries = hooks.get(event)
            if not isinstance(entries, list):
                continue
            kept = []
            for entry in entries:
                if sig in str(entry):
                    removed += 1
                    continue
                kept.append(entry)
            if kept:
                hooks[event] = kept
            else:
                hooks.pop(event, None)
        if removed == 0:
            return InstallResult(AGENT, agent_config_path, "already_present", "hook not present")
        if not hooks:
            data.pop("hooks", None)
        write_json(agent_config_path, data)
        return InstallResult(AGENT, agent_config_path, "removed", f"removed {removed} hook entry")
    except Exception as exc:
        return failure(AGENT, agent_config_path, exc)
