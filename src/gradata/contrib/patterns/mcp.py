"""MCP Integration — SDK abstraction over Model Context Protocol (Layer 0). Brain declares tool
schemas; host connects and routes calls. Schema/routing here; transport (stdio/SSE/HTTP) on host."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MCPToolSchema:
    """Schema for a tool exposed via MCP.

    Maps to the MCP tool definition format used by Claude Code,
    Cursor, and other MCP-compatible hosts.
    """

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)  # JSON Schema
    category: str = "brain"


@dataclass
class MCPServer:
    """Represents a connected MCP server."""

    name: str
    tools: list[MCPToolSchema] = field(default_factory=list)
    status: str = "connected"  # connected, disconnected, error


class MCPBridge:
    """Bridge between brain SDK and MCP protocol.

    Registers brain functions as MCP-compatible tools that can be
    discovered and called by any MCP host.
    """

    def __init__(self, brain_name: str = "gradata") -> None:
        self.brain_name = brain_name
        self._tools: dict[str, MCPToolSchema] = {}
        self._handlers: dict[str, Any] = {}  # name -> callable
        self._connected_servers: list[MCPServer] = []

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any] | None = None,
        handler: Any = None,
        category: str = "brain",
    ) -> None:
        """Register a brain function as an MCP tool."""
        schema = MCPToolSchema(
            name=name,
            description=description,
            input_schema=input_schema or {},
            category=category,
        )
        self._tools[name] = schema
        if handler is not None:
            self._handlers[name] = handler

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        """Export all tools as MCP-compatible JSON schemas.

        This is what gets sent to the host when it queries
        available tools via the MCP protocol.
        """
        return [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": {
                    "type": "object",
                    "properties": t.input_schema,
                },
            }
            for t in self._tools.values()
        ]

    def handle_call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Handle an incoming MCP tool call.

        Returns:
            Dict with "result" on success, "error" on failure.
        """
        handler = self._handlers.get(tool_name)
        if handler is None:
            return {"error": f"Unknown tool: {tool_name}"}
        try:
            result = handler(**arguments)
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}

    def stats(self) -> dict[str, Any]:
        """Bridge statistics."""
        return {
            "brain_tools": len(self._tools),
            "brain_handlers": len(self._handlers),
            "connected_servers": len(self._connected_servers),
            "total_external_tools": sum(len(s.tools) for s in self._connected_servers),
        }


def create_brain_mcp_tools() -> list[MCPToolSchema]:
    """Default MCP tool schemas for a brain.

    These are the standard operations every brain exposes via MCP.
    """
    return [
        MCPToolSchema(
            "brain_search",
            "Search the brain for relevant context",
            {"query": {"type": "string", "description": "Search query"}},
        ),
        MCPToolSchema(
            "brain_correct",
            "Record a user correction to improve the brain",
            {
                "draft": {"type": "string", "description": "Original AI draft"},
                "final": {"type": "string", "description": "User-edited final version"},
            },
        ),
        MCPToolSchema(
            "brain_log_output",
            "Log an AI-generated output for tracking",
            {
                "text": {"type": "string", "description": "Generated text"},
                "output_type": {"type": "string", "description": "Type of output"},
            },
        ),
        MCPToolSchema(
            "brain_manifest",
            "Generate and return brain quality manifest",
            {},
        ),
        MCPToolSchema(
            "brain_health",
            "Check brain health status",
            {},
        ),
    ]
