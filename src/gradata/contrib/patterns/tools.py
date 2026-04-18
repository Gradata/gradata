"""
Tool Registration — typed tool signatures with plan-before-execute.
===================================================================
Layer 0 pattern: domain-agnostic.

Provides a registry for tools the brain can use, with typed signatures,
description, and plan-before-execute workflow. Tools are registered by
the host (Claude Code hooks, MCP servers, custom scripts) and queried
by the brain's orchestrator and pipeline patterns.

This is the SDK abstraction layer. Actual tool execution happens in the
host runtime, not in the SDK.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(frozen=True)
class ToolSpec:
    """Typed specification for a registered tool.

    Domain-agnostic: works for any tool type — MCP tools, Python functions,
    shell commands, API endpoints.
    """

    name: str
    description: str
    parameters: dict[str, str] = field(default_factory=dict)  # param_name -> type hint
    returns: str = "Any"
    category: str = "general"  # grouping (e.g., "search", "write", "analyze")
    requires_confirmation: bool = False  # needs human approval before execution
    idempotent: bool = True  # safe to retry


@dataclass
class ToolResult:
    """Result of executing a tool."""

    tool: str
    success: bool
    output: Any = None
    error: str | None = None
    retries: int = 0


class ToolRegistry:
    """Registry of available tools.

    The brain's orchestrator queries this to determine what tools
    are available for a given task.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self._handlers: dict[str, Callable] = {}

    def register(
        self,
        spec: ToolSpec,
        handler: Callable | None = None,
    ) -> None:
        """Register a tool with optional handler.

        Args:
            spec: Tool specification.
            handler: Optional callable that executes the tool.
                     If None, tool is registered as metadata only
                     (execution happens in the host runtime).
        """
        self._tools[spec.name] = spec
        if handler is not None:
            self._handlers[spec.name] = handler

    def get(self, name: str) -> ToolSpec | None:
        """Look up a tool by name."""
        return self._tools.get(name)

    def list_tools(self, category: str | None = None) -> list[ToolSpec]:
        """List all registered tools, optionally filtered by category."""
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        return sorted(tools, key=lambda t: t.name)

    def categories(self) -> list[str]:
        """List all tool categories."""
        return sorted({t.category for t in self._tools.values()})

    def search(self, query: str) -> list[ToolSpec]:
        """Search tools by name or description keyword."""
        q = query.lower()
        return [
            t for t in self._tools.values()
            if q in t.name.lower() or q in t.description.lower()
        ]

    def execute(
        self,
        name: str,
        params: dict[str, Any] | None = None,
        max_retries: int = 1,
    ) -> ToolResult:
        """Execute a registered tool.

        Args:
            name: Tool name.
            params: Parameters to pass.
            max_retries: Retry count on failure (default 1 = no retry).

        Returns:
            ToolResult. If no handler registered, returns error result.
        """
        handler = self._handlers.get(name)
        if handler is None:
            return ToolResult(
                tool=name, success=False,
                error=f"No handler registered for '{name}'",
            )

        params = params or {}
        last_error = None
        for attempt in range(max_retries):
            try:
                output = handler(**params)
                return ToolResult(
                    tool=name, success=True, output=output, retries=attempt,
                )
            except Exception as e:
                last_error = str(e)

        return ToolResult(
            tool=name, success=False, error=last_error, retries=max_retries,
        )

    def stats(self) -> dict[str, Any]:
        """Registry statistics."""
        return {
            "total_tools": len(self._tools),
            "with_handlers": len(self._handlers),
            "categories": self.categories(),
        }


