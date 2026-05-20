"""Shared helpers for Gradata hook adapter installers + runtime extraction.

Adapters are the bridge between Gradata and a specific AI-coding-agent
host (Claude Code, Codex, Cursor, Gemini, Hermes, OpenCode). Each adapter
owns TWO concerns for its host:

1. **Install** — write the right hook/MCP wire-up into the host's config
   file (settings.json, config.toml, etc.). This is the only concern
   pre-2026-05-19.

2. **Runtime extraction** — given a stdin payload that the host pipes
   into ``python -m gradata.hooks.auto_correct``, decide whether the
   payload represents a "correction" (file edit) and return the
   ``(draft, final)`` tuple. Hosts disagree on stdin shape, tool names,
   and where the tool args live; centralising this per-adapter prevents
   the "extractor only works for one host" regression that bit oliver-
   admin for 43h in May 2026 (Gradata/gradata#TBD).

Each adapter is a module exposing:

- ``AGENT: str`` — canonical agent name (e.g. ``"hermes"``)
- ``install(brain_dir, agent_config_path) -> InstallResult``
- ``detect(payload: dict) -> bool`` — does this stdin look like this host?
- ``extract_correction(payload, tool_output=None) -> tuple[str, str] | None``

The dispatcher in ``auto_correct._extract_correction`` calls ``detect``
on each registered adapter in priority order, then routes to the first
match's ``extract_correction``. If no adapter claims the payload, the
generic ``extract_generic`` falls back to a duck-typed best-effort.

Contract test: ``tests/test_adapter_extraction_contracts.py`` runs a
fixed corpus of payloads through every registered adapter and asserts
each adapter's ``detect``/``extract_correction`` is honest (no false-
positive captures across hosts, no silent drops on its own host's
canonical shape).
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

from gradata._atomic import atomic_write_text

Action = Literal["added", "already_present", "failed", "removed"]

AGENTS = ("claude-code", "codex", "gemini", "cursor", "hermes", "opencode")
_MODULES = {
    "claude-code": "claude_code",
    "codex": "codex",
    "gemini": "gemini",
    "cursor": "cursor",
    "hermes": "hermes",
    "opencode": "opencode",
}
_CONFIGS = {
    "claude-code": Path(".claude/settings.json"),
    "codex": Path(".codex/config.toml"),
    "gemini": Path(".gemini/settings.json"),
    "cursor": Path(".cursor/mcp.json"),
    "hermes": Path(".hermes/config.yaml"),
    "opencode": Path(".config/opencode/config.json"),
}
# Detection priority — most-specific hosts first. Hermes carries an
# unmistakable ``hook_event_name`` envelope; Claude Code has the original
# ``Edit``/``Write`` capitalised tool names; the others use generic
# lowercase tool names so they fall through to detection-by-elimination.
_DETECT_PRIORITY = ("hermes", "claude-code", "codex", "opencode", "gemini", "cursor")

logger = logging.getLogger(__name__)


@runtime_checkable
class HostAdapter(Protocol):
    """Structural protocol every adapter module must satisfy."""

    AGENT: str

    def install(self, brain_dir: Path, agent_config_path: Path) -> InstallResult: ...
    def detect(self, payload: dict) -> bool: ...
    def extract_correction(
        self, payload: dict, tool_output: dict | str | None = None
    ) -> tuple[str, str] | None: ...


@dataclass(frozen=True)
class InstallResult:
    agent: str
    config_path: Path
    action: Action
    message: str


def adapter_config_path(agent: str, *, home: Path | None = None) -> Path:
    if agent not in _CONFIGS:
        raise ValueError(f"unknown agent: {agent}")
    resolved_home = home or _resolve_home_dir()
    return resolved_home / _CONFIGS[agent]


def _resolve_home_dir() -> Path:
    return Path(os.environ.get("HOME") or os.environ.get("USERPROFILE") or os.path.expanduser("~"))


def get_adapter(agent: str):
    if agent not in _MODULES:
        raise ValueError(f"unknown agent: {agent}")
    return importlib.import_module(f"gradata.hooks.adapters.{_MODULES[agent]}")


def iter_adapters_in_priority_order():
    """Yield adapter modules in detection priority order.

    The dispatcher walks this in order and routes the payload to the
    first adapter whose ``detect()`` returns True.
    """
    for agent in _DETECT_PRIORITY:
        yield agent, get_adapter(agent)


def hook_signature(agent: str, brain_dir: Path) -> str:
    return f"gradata:{agent}:{brain_dir.resolve().as_posix()}"


def hook_command(brain_dir: Path) -> str:
    return (
        f"BRAIN_DIR={shlex.quote(str(brain_dir))} "
        f"{shlex.quote(sys.executable)} -m gradata.hooks.inject_brain_rules"
    )


def mcp_command(brain_dir: Path) -> list[str]:
    return [sys.executable, "-m", "gradata.mcp_server", "--brain-dir", str(brain_dir)]


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.warning("failed to read JSON config %s", path, exc_info=True)
        raise
    if not isinstance(data, dict):
        raise TypeError(f"JSON config must contain an object: {path}")
    return data


def write_json(path: Path, data: dict) -> None:
    atomic_write_text(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def contains_signature(path: Path, signature: str) -> bool:
    return path.exists() and signature in path.read_text(encoding="utf-8", errors="replace")


def failure(agent: str, config_path: Path, exc: Exception) -> InstallResult:
    return InstallResult(agent, config_path, "failed", str(exc))


def uninstall_from_list_in_dict(
    *,
    agent: str,
    brain_dir: Path,
    agent_config_path: Path,
    outer_key: str,
    inner_key: str,
) -> InstallResult:
    """Generic uninstall helper for JSON configs shaped as ``{outer:{inner:[entries]}}``.

    Used by gemini (tools.preCall), opencode (hooks.preTool), hermes
    (hooks.pre_tool_call). Removes every entry whose ``str(entry)``
    contains our ``hook_signature(agent, brain_dir)``. Idempotent.
    Empty containers are pruned.
    """
    try:
        if not agent_config_path.is_file():
            return InstallResult(
                agent, agent_config_path, "already_present", "config file does not exist"
            )
        sig = hook_signature(agent, brain_dir)
        data = read_json(agent_config_path)
        outer = data.get(outer_key)
        if not isinstance(outer, dict):
            return InstallResult(
                agent, agent_config_path, "already_present", f"no {outer_key} block"
            )
        entries = outer.get(inner_key)
        if not isinstance(entries, list):
            return InstallResult(
                agent, agent_config_path, "already_present", f"no {outer_key}.{inner_key}"
            )

        removed = 0
        kept: list = []
        for entry in entries:
            if sig in str(entry):
                removed += 1
                continue
            kept.append(entry)
        if removed == 0:
            return InstallResult(agent, agent_config_path, "already_present", "hook not present")

        if kept:
            outer[inner_key] = kept
        else:
            outer.pop(inner_key, None)
        if not outer:
            data.pop(outer_key, None)
        write_json(agent_config_path, data)
        return InstallResult(agent, agent_config_path, "removed", f"removed {removed} hook entry")
    except Exception as exc:
        return failure(agent, agent_config_path, exc)


# --------------------------------------------------------------------------
# Shared extraction utilities — used by individual adapters.
# --------------------------------------------------------------------------


def _coerce_dict(value) -> dict:
    """Return value if it's a non-empty dict, else {}."""
    return value if isinstance(value, dict) else {}


def _normalize_tool_name(raw: str) -> str:
    """Strip framework-specific prefixes for matching.

    - Hermes MCP tools arrive as ``mcp_<RawName>`` — strip ``mcp_``.
    - Some hosts include namespacing like ``builtin:Edit`` — strip prefix up to ``:``.
    """
    name = raw or ""
    if name.startswith("mcp_"):
        name = name[4:]
    if ":" in name:
        name = name.rsplit(":", 1)[-1]
    return name


# Tool-name allowlists at the adapter layer below. Adapter modules import
# these as the canonical "what counts as an edit/write" enumeration and
# extend per host where the host's tool surface is documented to include
# additional aliases.

EDIT_TOOL_ALIASES = frozenset(
    {
        "Edit",
        "edit",
        "MultiEdit",
        "patch",
        "Patch",
        "str_replace",
        "string_replace",
        "string_replace_editor",
        "apply_patch",
    }
)

WRITE_TOOL_ALIASES = frozenset(
    {
        "Write",
        "write",
        "write_file",
        "Write_file",
        "create_file",
        "createFile",
        "NewFile",
    }
)


def extract_from_edit_args(args: dict) -> tuple[str, str] | None:
    """Edit-class tools: pull ``old_string`` and ``new_string`` from args."""
    old = args.get("old_string") or args.get("oldString") or ""
    new = args.get("new_string") or args.get("newString") or ""
    if old and new and old != new:
        return (old, new)
    return None


def extract_from_write_args(args: dict, tool_output) -> tuple[str, str] | None:
    """Write-class tools: full-file replacement requires the host to supply
    the previous file content via ``tool_output.old_content``. Hosts that
    don't surface old_content produce no correction (we can't fabricate
    one from thin air without reading the filesystem, which the hook
    should not do)."""
    new_content = args.get("content") or args.get("file_text") or ""
    out = _coerce_dict(tool_output)
    old_content = out.get("old_content") or out.get("oldContent") or ""
    if old_content and new_content and old_content != new_content:
        return (old_content[:5000], new_content[:5000])
    return None
