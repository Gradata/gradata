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

AGENT = "claude-code"
HOOKS: tuple[tuple[str, str | None, str], ...] = (
    ("PreToolUse", "*", "inject_brain_rules"),
    ("PostToolUse", "Edit|Write", "auto_correct"),
    ("Stop", None, "session_close"),
    ("PreCompact", "manual|auto", "pre_compact"),
    ("UserPromptSubmit", None, "context_inject"),
)

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
        if _has_exact_installed_hook_set(hooks, sig):
            return InstallResult(
                AGENT, agent_config_path, "already_present", "hook already present"
            )
        for event, matcher, module in HOOKS:
            _remove_existing_module_hook(hooks, event, module)
            group = {
                "matcher": "*",
                "hooks": [
                    {
                        "type": "command",
                        "command": hook_command(brain_dir, module),
                        "id": f"{sig}:{event}:{module}",
                    }
                ],
            }
            if matcher is None:
                group.pop("matcher")
            else:
                group["matcher"] = matcher
            hooks.setdefault(event, []).append(group)
        write_json(agent_config_path, data)
        return InstallResult(AGENT, agent_config_path, "added", "installed Claude Code hooks")
    except Exception as exc:
        return failure(AGENT, agent_config_path, exc)


def _is_gradata_module_hook(item: object, event: str, module: str) -> bool:
    text = str(item)
    return f"gradata.hooks.{module}" in text or (
        f"gradata:{AGENT}:" in text and f":{event}:{module}" in text
    )


def _has_exact_installed_hook_set(hooks: dict, sig: str) -> bool:
    """Return true only when every Gradata module hook is the desired one."""
    for event, _matcher, module in HOOKS:
        entries = hooks.get(event)
        if not isinstance(entries, list):
            return False
        module_entries = [
            entry for entry in entries if _is_gradata_module_hook(entry, event, module)
        ]
        if len(module_entries) != 1:
            return False
        if f"{sig}:{event}:{module}" not in str(module_entries[0]):
            return False
    return True


def _remove_existing_module_hook(hooks: dict, event: str, module: str) -> None:
    entries = hooks.get(event)
    if not isinstance(entries, list):
        return
    kept_groups: list = []
    for group in entries:
        if not isinstance(group, dict):
            if not _is_gradata_module_hook(group, event, module):
                kept_groups.append(group)
            continue
        group_hooks = group.get("hooks")
        if not isinstance(group_hooks, list):
            if not _is_gradata_module_hook(group, event, module):
                kept_groups.append(group)
            continue
        kept_hooks = [
            hook for hook in group_hooks if not _is_gradata_module_hook(hook, event, module)
        ]
        if kept_hooks:
            new_group = dict(group)
            new_group["hooks"] = kept_hooks
            kept_groups.append(new_group)
    if kept_groups:
        hooks[event] = kept_groups
    else:
        hooks.pop(event, None)


def uninstall(brain_dir: Path, agent_config_path: Path) -> InstallResult:
    """Reverse ``install()`` across all hook events.

    Idempotent — calling on an already-clean config returns ``already_present``
    (semantically: 'already in the desired absent state'). Empty containers
    are pruned. User-owned entries (without our signature) are preserved
    verbatim while every signature-matching Gradata entry is removed.
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
        removed = 0
        for event in list(hooks):
            entries = hooks.get(event)
            if not isinstance(entries, list):
                continue
            kept: list = []
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
