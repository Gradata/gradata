from __future__ import annotations

import json
from pathlib import Path

from gradata._atomic import atomic_write_text
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
)

AGENT = "codex"
HOOKS: tuple[tuple[str, str], ...] = (
    ("pre_tool", "inject_brain_rules"),
    ("post_tool", "auto_correct"),
    ("session_end", "session_close"),
)

# Codex's edit/write tool surface (OpenAI Codex CLI documented tool names).
CODEX_EDIT_TOOLS = EDIT_TOOL_ALIASES | frozenset({"apply_patch", "str_replace_editor"})
CODEX_WRITE_TOOLS = WRITE_TOOL_ALIASES


def detect(payload: dict) -> bool:
    """Codex stdin: ``{"tool": "apply_patch", "input": {...}}``.

    Distinguishing features:
    - ``tool`` field present (not ``tool_name``) — rules out Claude Code
    - ``input`` field present (not ``args``)         — rules out Gemini
    - ``event`` field absent                          — rules out OpenCode
    - ``hook_event_name`` absent                      — rules out Hermes
    - tool name in Codex's edit/write surface
    """
    if not isinstance(payload, dict):
        return False
    if payload.get("hook_event_name"):
        return False
    if payload.get("event") in {"preTool", "postTool"}:
        return False
    if "tool" not in payload:
        return False
    if "input" not in payload:
        return False
    if "args" in payload:
        return False
    tool_name = _normalize_tool_name(payload.get("tool") or "")
    return tool_name in CODEX_EDIT_TOOLS or tool_name in CODEX_WRITE_TOOLS


def extract_correction(
    payload: dict, tool_output: dict | str | None = None
) -> tuple[str, str] | None:
    # Codex uses the lowercase ``tool`` field only.
    tool_name = _normalize_tool_name(payload.get("tool") or "")
    args = payload.get("input")
    if not isinstance(args, dict):
        return None

    if tool_name in CODEX_EDIT_TOOLS:
        return extract_from_edit_args(args)
    if tool_name in CODEX_WRITE_TOOLS:
        return extract_from_write_args(args, tool_output)
    return None


def _toml_string(value: str) -> str:
    return json.dumps(value)


def install(brain_dir: Path, agent_config_path: Path) -> InstallResult:
    try:
        sig = hook_signature(AGENT, brain_dir)
        existing = (
            agent_config_path.read_text(encoding="utf-8") if agent_config_path.exists() else ""
        )
        if _has_exact_installed_hook_set(existing, sig):
            return InstallResult(
                AGENT, agent_config_path, "already_present", "hook already present"
            )
        cleaned = _remove_gradata_hook_tables(existing)
        blocks = []
        for event, module in HOOKS:
            blocks.append(
                f"[[hooks.{event}]]\n"
                f"id = {_toml_string(f'{sig}:{event}:{module}')}\n"
                f"command = {_toml_string(hook_command(brain_dir, module))}\n"
            )
        atomic_write_text(agent_config_path, cleaned.rstrip() + "\n" + "\n".join(blocks))
        return InstallResult(AGENT, agent_config_path, "added", "installed Codex hooks")
    except Exception as exc:
        return failure(AGENT, agent_config_path, exc)


def _is_gradata_module_table(table: list[str], module: str | None = None) -> bool:
    text = "".join(table)
    if "gradata.hooks." not in text and f"gradata:{AGENT}:" not in text:
        return False
    if module is None:
        return True
    return f"gradata.hooks.{module}" in text or f":{module}" in text


def _split_toml_tables(text: str) -> list[list[str]]:
    tables: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith("[[") or stripped.startswith("["):
            if current:
                tables.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        tables.append(current)
    return tables


def _remove_gradata_hook_tables(text: str) -> str:
    kept: list[str] = []
    for table in _split_toml_tables(text):
        header = table[0].lstrip() if table else ""
        if header.startswith("[[hooks.") and _is_gradata_module_table(table):
            continue
        kept.extend(table)
    return "".join(kept).rstrip() + ("\n" if kept else "")


def _has_exact_installed_hook_set(text: str, sig: str) -> bool:
    for event, module in HOOKS:
        expected_header = f"[[hooks.{event}]]"
        expected_id = f"{sig}:{event}:{module}"
        matches = [
            table
            for table in _split_toml_tables(text)
            if table and table[0].strip() == expected_header and _is_gradata_module_table(table, module)
        ]
        if len(matches) != 1 or expected_id not in "".join(matches[0]):
            return False
    return True


def uninstall(brain_dir: Path, agent_config_path: Path) -> InstallResult:
    """Reverse install: drop Codex hook blocks carrying our signature.

    Operates on the raw TOML text — walks line-by-line, identifies hook
    tables that contain our signature, and removes those tables + keys.
    Preserves all other tables verbatim.
    """
    try:
        if not agent_config_path.is_file():
            return InstallResult(
                AGENT, agent_config_path, "already_present", "config file does not exist"
            )
        sig = hook_signature(AGENT, brain_dir)
        text = agent_config_path.read_text(encoding="utf-8")
        if sig not in text:
            return InstallResult(AGENT, agent_config_path, "already_present", "hook not present")

        # Walk by table-headers. A new table starts at any line matching
        # `^\[` (single or double bracket). Drop the table that contains
        # our sig.
        out_lines: list[str] = []
        current_table: list[str] = []
        current_is_hook = False
        removed = 0

        def flush(buf: list[str], is_hook: bool) -> None:
            nonlocal removed
            if not buf:
                return
            if is_hook and any(sig in line for line in buf):
                removed += 1
                return  # drop the whole table
            out_lines.extend(buf)

        for line in text.splitlines(keepends=True):
            stripped = line.lstrip()
            if stripped.startswith("[[") or stripped.startswith("["):
                # Flush the previous table
                flush(current_table, current_is_hook)
                current_table = [line]
                current_is_hook = stripped.startswith("[[hooks.")
            else:
                if current_table:
                    current_table.append(line)
                else:
                    out_lines.append(line)
        # Final flush
        flush(current_table, current_is_hook)

        if removed == 0:
            return InstallResult(
                AGENT, agent_config_path, "already_present", "hook table not present"
            )

        new_text = "".join(out_lines).rstrip() + "\n"
        atomic_write_text(agent_config_path, new_text)
        return InstallResult(
            AGENT, agent_config_path, "removed", f"removed {removed} Codex hook block"
        )
    except Exception as exc:
        return failure(AGENT, agent_config_path, exc)
