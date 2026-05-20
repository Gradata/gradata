from __future__ import annotations

from pathlib import Path

from gradata.hooks.adapters._base import InstallResult, failure, mcp_command, read_json, write_json

AGENT = "cursor"


def detect(payload: dict) -> bool:
    """Cursor integrates via MCP, not via stdin hooks.

    Corrections are captured through the gradata MCP server's tool
    surface (``brain_correct`` tool callable from Cursor's chat), not
    through a stdin pipe to this script. So no stdin payload should be
    routed to this adapter — detect always returns False.
    """
    return False


def extract_correction(
    payload: dict, tool_output: dict | str | None = None
) -> tuple[str, str] | None:
    """Cursor doesn't emit auto_correct stdin payloads; nothing to extract."""
    return None


def install(brain_dir: Path, agent_config_path: Path) -> InstallResult:
    try:
        data = read_json(agent_config_path)
        servers = data.setdefault("mcpServers", {})
        existing = servers.get("gradata")
        mcp = mcp_command(brain_dir)
        command, args = mcp[0], mcp[1:]
        if (
            isinstance(existing, dict)
            and existing.get("command") == command
            and existing.get("args") == args
        ):
            return InstallResult(
                AGENT, agent_config_path, "already_present", "MCP server already present"
            )
        desired = existing if isinstance(existing, dict) else {}
        desired["command"] = command
        desired["args"] = args
        servers["gradata"] = desired
        write_json(agent_config_path, data)
        return InstallResult(AGENT, agent_config_path, "added", "installed MCP server")
    except Exception as exc:
        return failure(AGENT, agent_config_path, exc)


def uninstall(brain_dir: Path, agent_config_path: Path) -> InstallResult:
    """Reverse install: drop the ``gradata`` entry from ``mcpServers``."""
    try:
        if not agent_config_path.is_file():
            return InstallResult(
                AGENT, agent_config_path, "already_present", "config file does not exist"
            )
        data = read_json(agent_config_path)
        servers = data.get("mcpServers")
        if not isinstance(servers, dict) or "gradata" not in servers:
            return InstallResult(
                AGENT, agent_config_path, "already_present", "MCP server not present"
            )
        servers.pop("gradata", None)
        if not servers:
            data.pop("mcpServers", None)
        write_json(agent_config_path, data)
        return InstallResult(AGENT, agent_config_path, "removed", "removed MCP server")
    except Exception as exc:
        return failure(AGENT, agent_config_path, exc)
