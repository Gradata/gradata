from __future__ import annotations

from pathlib import Path

from gradata.hooks.adapters._base import InstallResult, failure, mcp_command, read_json, write_json

AGENT = "cursor"


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
