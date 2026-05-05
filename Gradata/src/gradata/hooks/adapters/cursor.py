from __future__ import annotations

from pathlib import Path

from gradata.hooks.adapters._base import InstallResult, failure, mcp_command, read_json, write_json

AGENT = "cursor"


def install(brain_dir: Path, agent_config_path: Path) -> InstallResult:
    try:
        data = read_json(agent_config_path)
        servers = data.setdefault("mcpServers", {})
        existing = servers.get("gradata")
        command = mcp_command(brain_dir)
        desired = {"command": command[0], "args": command[1:]}
        if existing == desired:
            return InstallResult(
                AGENT, agent_config_path, "already_present", "MCP server already present"
            )
        servers["gradata"] = desired
        write_json(agent_config_path, data)
        return InstallResult(AGENT, agent_config_path, "added", "installed MCP server")
    except Exception as exc:
        return failure(AGENT, agent_config_path, exc)
