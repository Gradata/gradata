from __future__ import annotations

from pathlib import Path

from gradata._atomic import atomic_write_text
from gradata.hooks.adapters._base import (
    InstallResult,
    contains_signature,
    failure,
    hook_command,
    hook_signature,
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
        if contains_signature(agent_config_path, sig):
            return InstallResult(
                AGENT, agent_config_path, "already_present", "hook already present"
            )

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
        pre_tool_call = _migrate_legacy_event(hooks, "pre_tool_use", "pre_tool_call")
        if any(isinstance(entry, dict) and entry.get("id") == sig for entry in pre_tool_call):
            return InstallResult(
                AGENT, agent_config_path, "already_present", "hook already present"
            )
        pre_tool_call.append({"id": sig, "command": hook_command(brain_dir)})
        atomic_write_text(agent_config_path, _dump_simple_yaml(data))
        return InstallResult(AGENT, agent_config_path, "added", "installed pre_tool_call hook")
    except Exception as exc:
        return failure(AGENT, agent_config_path, exc)
