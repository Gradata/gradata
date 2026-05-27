from __future__ import annotations

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
    post_tool_hook_command,
    session_end_hook_command,
)

AGENT = "hermes"

# Hermes recognises these event names natively. The Claude-Code event names
# (pre_tool_use / post_tool_use / session_end) are *silently ignored* by the
# Hermes runtime — only a warning is logged. Earlier versions of this adapter
# wrote the Claude-Code names by mistake, so we also accept the legacy keys
# here on read and migrate them on write.
HERMES_EVENT_NAMES: dict[str, str] = {
    "pre_tool_use": "pre_tool_call",
    "post_tool_use": "post_tool_call",
    "session_end": "on_session_end",
}


def _migrate_legacy_event(hooks: dict, legacy_key: str, current_key: str) -> list:
    """Return the list living at *current_key*, folding any entries that were
    historically written under *legacy_key* into it. Removes the legacy key
    once its entries have been migrated so an old broken install becomes a
    correct one the next time the user runs ``gradata install --agent hermes``.
    """
    current = hooks.setdefault(current_key, [])
    if not isinstance(current, list):
        current = []
        hooks[current_key] = current
    legacy = hooks.get(legacy_key)
    if isinstance(legacy, list):
        for entry in legacy:
            if entry not in current:
                current.append(entry)
        del hooks[legacy_key]
    elif legacy_key in hooks:
        # Malformed legacy value (not a list) — drop it; the new key owns the
        # event from here on.
        del hooks[legacy_key]
    return current


def _parse_simple_yaml(text: str) -> dict:
    """Parse the small Hermes config shape without requiring PyYAML."""
    data: dict = {}
    current_key: str | None = None
    current_list: list | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not raw.startswith(" ") and line.endswith(":"):
            current_key = line[:-1].strip()
            data[current_key] = {}
            current_list = None
            continue
        if not raw.startswith(" ") and ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = _parse_scalar(value.strip())
            current_key = None
            current_list = None
            continue
        if current_key is None:
            continue
        stripped = line.strip()
        container = data.setdefault(current_key, {})
        if stripped.endswith(":") and not stripped.startswith("- "):
            nested_key = stripped[:-1]
            if isinstance(container, dict):
                current_list = []
                container[nested_key] = current_list
            continue
        if stripped.startswith("- "):
            if current_list is None:
                current_list = []
                if isinstance(container, dict):
                    container.setdefault("items", current_list)
            item_text = stripped[2:].strip()
            if ":" in item_text:
                key, value = item_text.split(":", 1)
                current_list.append({key.strip(): _parse_scalar(value.strip())})
            else:
                current_list.append(_parse_scalar(item_text))
            continue
        if (
            current_list is not None
            and current_list
            and isinstance(current_list[-1], dict)
            and ":" in stripped
        ):
            key, value = stripped.split(":", 1)
            current_list[-1][key.strip()] = _parse_scalar(value.strip())
    return data


def _parse_scalar(value: str):
    if not value:
        return ""
    if value in ("true", "false"):
        return value == "true"
    return value.strip("'\"")


def _dump_simple_yaml(data: dict, indent: int = 0) -> str:
    lines: list[str] = []
    pad = " " * indent
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{pad}{key}:")
            lines.append(_dump_simple_yaml(value, indent + 2).rstrip())
        elif isinstance(value, list):
            lines.append(f"{pad}{key}:")
            for item in value:
                if isinstance(item, dict):
                    first = True
                    for child_key, child_value in item.items():
                        prefix = "- " if first else "  "
                        lines.append(f"{pad}  {prefix}{child_key}: {_format_scalar(child_value)}")
                        first = False
                else:
                    lines.append(f"{pad}  - {_format_scalar(item)}")
        else:
            lines.append(f"{pad}{key}: {_format_scalar(value)}")
    return "\n".join(line for line in lines if line) + "\n"


def _format_scalar(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value)
    if any(ch in text for ch in (":", "#", "{", "}", "[", "]")):
        return repr(text)
    return text


def install(brain_dir: Path, agent_config_path: Path) -> InstallResult:
    try:
        sig = hook_signature(AGENT, brain_dir)
        existing = (
            agent_config_path.read_text(encoding="utf-8") if agent_config_path.exists() else ""
        )
        loaded = _parse_simple_yaml(existing) if existing.strip() else {}
        data = loaded if isinstance(loaded, dict) else {}
        hooks = data.setdefault("hooks", {})
        if not isinstance(hooks, dict):
            hooks = {}
            data["hooks"] = hooks
        # Hermes uses *_tool_call / on_session_end event names. Writing the
        # Claude-Code names (pre_tool_use / post_tool_use / session_end) here
        # results in Hermes silently ignoring the entries (warning only). See
        # Gradata/gradata#190 for the install-UX epic.
        added: list[str] = []
        for current_key, legacy_key, command in (
            ("pre_tool_call", "pre_tool_use", hook_command(brain_dir)),
            ("post_tool_call", "post_tool_use", post_tool_hook_command(brain_dir)),
            ("on_session_end", "session_end", session_end_hook_command(brain_dir)),
        ):
            entries = _migrate_legacy_event(hooks, legacy_key, current_key)
            if any(isinstance(entry, dict) and entry.get("id") == sig for entry in entries):
                continue
            entries.append({"id": sig, "command": command})
            added.append(current_key)
        if not added:
            return InstallResult(
                AGENT, agent_config_path, "already_present", "hooks already present"
            )
        atomic_write_text(agent_config_path, _dump_simple_yaml(data))
        return InstallResult(
            AGENT,
            agent_config_path,
            "added",
            "installed pre_tool_call, post_tool_call, and on_session_end hooks",
        )
    except Exception as exc:
        return failure(AGENT, agent_config_path, exc)


# Hermes-specific tool name aliases (in addition to the universal allowlist).
# Hermes ships ``patch``/``write_file``/``mcp_*`` natively; MCP-dispatched
# tools arrive as ``mcp_<RawName>`` and need the prefix stripped (done by
# ``_normalize_tool_name``). See agent/shell_hooks.py::_serialize_payload
# in the Hermes runtime for the canonical wire shape.
HERMES_EDIT_TOOLS = EDIT_TOOL_ALIASES | frozenset({"patch", "Patch"})
HERMES_WRITE_TOOLS = WRITE_TOOL_ALIASES | frozenset({"write_file", "Write_file"})


def detect(payload: dict) -> bool:
    """Hermes stdin signature: top-level ``hook_event_name`` envelope.

    Hermes is the only host that wraps its payload with
    ``{"hook_event_name": "pre_tool_call" | "post_tool_call" | ...}``
    AND nests the tool args under ``tool_input``. Both signals are
    checked because some legacy migrations may emit only one.
    """
    if not isinstance(payload, dict):
        return False
    if payload.get("hook_event_name") in {
        "pre_tool_call",
        "post_tool_call",
        "on_session_end",
        "pre_llm_call",
    }:
        return True
    # Fallback: payload uses ``tool_input`` (not ``input``) AND has lowercase
    # tool name. This catches old Hermes versions before hook_event_name
    # was added, plus any Hermes-shape relay that strips the envelope.
    if "tool_input" in payload and "input" not in payload:
        tool_name = _normalize_tool_name(payload.get("tool_name") or "")
        if tool_name in HERMES_EDIT_TOOLS or tool_name in HERMES_WRITE_TOOLS:
            return True
    return False


def extract_correction(
    payload: dict, tool_output: dict | str | None = None
) -> tuple[str, str] | None:
    """Extract (draft, final) from a Hermes post_tool_call payload."""
    tool_name = _normalize_tool_name(payload.get("tool_name") or "")
    args = payload.get("tool_input")
    if not isinstance(args, dict):
        return None

    if tool_name in HERMES_EDIT_TOOLS:
        return extract_from_edit_args(args)
    if tool_name in HERMES_WRITE_TOOLS:
        return extract_from_write_args(args, tool_output)
    return None


def uninstall(brain_dir: Path, agent_config_path: Path) -> InstallResult:
    """Reverse install: drop signature-matching hook entries.

    Hermes uses YAML, so we can't reuse the generic JSON helper.
    Idempotent. Preserves user-owned entries and other hook events.
    """
    try:
        if not agent_config_path.is_file():
            return InstallResult(
                AGENT, agent_config_path, "already_present", "config file does not exist"
            )
        sig = hook_signature(AGENT, brain_dir)
        existing = agent_config_path.read_text(encoding="utf-8")
        if sig not in existing:
            return InstallResult(AGENT, agent_config_path, "already_present", "hook not present")
        loaded = _parse_simple_yaml(existing) if existing.strip() else {}
        data = loaded if isinstance(loaded, dict) else {}
        hooks = data.get("hooks") if isinstance(data, dict) else None
        if not isinstance(hooks, dict):
            return InstallResult(AGENT, agent_config_path, "already_present", "no hooks block")

        removed = 0
        # Check current and legacy event names.
        for key in (
            "pre_tool_call",
            "post_tool_call",
            "on_session_end",
            "pre_tool_use",
            "post_tool_use",
            "session_end",
        ):
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
        atomic_write_text(agent_config_path, _dump_simple_yaml(data))
        return InstallResult(AGENT, agent_config_path, "removed", f"removed {removed} hook entry")
    except Exception as exc:
        return failure(AGENT, agent_config_path, exc)
