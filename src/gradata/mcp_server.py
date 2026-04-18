"""
MCP Server — JSON-RPC 2.0 stdio transport for the Gradata.
=================================================================
Implements the Model Context Protocol (MCP) over stdin/stdout so any
MCP-compatible host (Claude Code, Cursor, VS Code Copilot Chat, etc.)
can call brain tools directly.

Protocol overview:
    - Messages are framed with HTTP-like headers:
          Content-Length: <N>\\r\\n\\r\\n<json>
    - Each message is a JSON-RPC 2.0 object (request or notification).
    - Lifecycle: initialize -> notifications/initialized -> tool calls -> shutdown

Usage:
    python -m gradata.mcp_server --brain-dir /path/to/brain

Tools exposed:
    brain_search(query, top_k)              Search brain knowledge
    brain_correct(draft, final)             Log a correction
    brain_log_output(text, output_type,     Log AI output
                     self_score)
    brain_manifest()                        Return quality manifest
    brain_health()                          Return health report
"""

from __future__ import annotations

import logging

_log = logging.getLogger("gradata.mcp_server")

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import io

# Import Brain at module level so tests can patch gradata.mcp_server.Brain.
# The import is guarded so the module stays usable even if the brain package
# has missing optional dependencies at collection time.
try:
    from .brain import Brain
except Exception:
    Brain = None  # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SERVER_NAME = "gradata"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2024-11-05"

# ---------------------------------------------------------------------------
# Framing helpers
# ---------------------------------------------------------------------------


def _read_message(stream: io.RawIOBase) -> dict[str, Any] | None:
    """Read one Content-Length-framed JSON-RPC message from *stream*.

    Returns the parsed dict, or None on EOF / framing error.
    """
    # Read headers until blank line
    header_bytes = b""
    while True:
        ch = stream.read(1)
        if not ch:
            return None  # EOF
        header_bytes += ch
        if header_bytes.endswith(b"\r\n\r\n"):
            break

    headers: dict[str, str] = {}
    for line in header_bytes.split(b"\r\n"):
        line = line.strip()
        if b":" in line:
            key, _, val = line.partition(b":")
            headers[key.strip().decode()] = val.strip().decode()

    _MAX_MESSAGE_BYTES = 10 * 1024 * 1024  # 10 MB — generous for any brain payload
    content_length = int(headers.get("Content-Length", 0))
    if content_length <= 0 or content_length > _MAX_MESSAGE_BYTES:
        return None

    body = b""
    remaining = content_length
    while remaining > 0:
        chunk = stream.read(remaining)
        if not chunk:
            return None
        body += chunk
        remaining -= len(chunk)

    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return None


def _write_message(stream: io.RawIOBase, obj: dict[str, Any]) -> None:
    """Write one Content-Length-framed JSON-RPC message to *stream*."""
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode()
    stream.write(header + body)
    stream.flush()


# ---------------------------------------------------------------------------
# JSON-RPC helpers
# ---------------------------------------------------------------------------

METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


def _ok(req_id: Any, result: Any) -> dict[str, Any]:
    """Build a successful JSON-RPC 2.0 response."""
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(req_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    """Build a JSON-RPC 2.0 error response."""
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": error}


# ---------------------------------------------------------------------------
# Tool schemas (MCP format)
# ---------------------------------------------------------------------------

_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "brain_search",
        "description": "Search the brain for relevant knowledge and context.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "top_k": {
                    "type": "integer",
                    "description": "Maximum results to return (default 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "brain_correct",
        "description": "Log a correction: the user edited an AI draft into a final version.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "draft": {"type": "string", "description": "Original AI-generated draft"},
                "final": {"type": "string", "description": "User-edited final version"},
            },
            "required": ["draft", "final"],
        },
    },
    {
        "name": "brain_log_output",
        "description": "Log an AI-generated output for quality tracking.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "AI-generated text"},
                "output_type": {
                    "type": "string",
                    "description": "Category of output (email, code, research, etc.)",
                    "default": "general",
                },
                "self_score": {
                    "type": "number",
                    "description": "Self-assessed quality score 0–10",
                },
            },
            "required": ["text"],
        },
    },
    {
        "name": "brain_manifest",
        "description": "Generate and return the brain quality manifest.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "brain_health",
        "description": "Return a brain health report.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "brain_pipeline_stats",
        "description": "Return procedural memory pipeline statistics: stages, router, context bracket, clusters.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "brain_context_bracket",
        "description": "Get current context degradation bracket (FRESH/MODERATE/DEEP/CRITICAL).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "brain_route_suggest",
        "description": "Suggest the best agent for a task using the Q-Learning router.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "Task description to route"},
            },
            "required": ["task"],
        },
    },
    {
        "name": "brain_capabilities",
        "description": "List SDK capabilities with source attribution (which modules are active).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "brain_benchmark",
        "description": "Run the standard procedural memory quality benchmark.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "brain_briefing",
        "description": "Generate a portable brain briefing (markdown) that any AI agent can consume.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------


def _dispatch(brain: Any, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Route a tool call to the appropriate brain method.

    Args:
        brain: A ``Brain`` instance (or None if not yet initialised).
        tool_name: MCP tool name.
        arguments: Validated argument dict from the MCP client.

    Returns:
        A dict ready to embed as the ``result`` of a JSON-RPC response.
        Always returns a dict; never raises.
    """
    if brain is None:
        return {"error": "Brain not initialized. Pass --brain-dir at startup."}

    try:
        if tool_name == "brain_search":
            query = arguments.get("query", "")
            top_k = int(arguments.get("top_k", 5))
            results = brain.search(query, top_k=top_k)
            return {
                "content": [
                    {"type": "text", "text": json.dumps(results, ensure_ascii=False)}
                ]
            }

        elif tool_name == "brain_correct":
            draft = arguments.get("draft", "")
            final = arguments.get("final", "")
            result = brain.correct(draft, final)
            # correct() returns dataclass objects that aren't JSON-serializable.
            # Extract the serializable summary from result["data"].
            data = result.get("data", {})
            summary = {
                "severity": data.get("severity", "unknown"),
                "edit_distance": data.get("edit_distance", 0),
                "category": data.get("category", "UNKNOWN"),
                "major_edit": data.get("major_edit", False),
                "summary": data.get("summary", ""),
                "ts": result.get("ts", ""),
            }
            return {
                "content": [
                    {"type": "text", "text": json.dumps(summary, ensure_ascii=False)}
                ]
            }

        elif tool_name == "brain_log_output":
            text = arguments.get("text", "")
            output_type = arguments.get("output_type", "general")
            self_score = arguments.get("self_score")
            result = brain.log_output(text, output_type=output_type, self_score=self_score)
            safe = {
                k: v
                for k, v in result.items()
                if isinstance(v, (str, int, float, bool, list, dict, type(None)))
            }
            return {
                "content": [
                    {"type": "text", "text": json.dumps(safe, ensure_ascii=False)}
                ]
            }

        elif tool_name == "brain_manifest":
            manifest = brain.manifest()
            return {
                "content": [
                    {"type": "text", "text": json.dumps(manifest, ensure_ascii=False)}
                ]
            }

        elif tool_name == "brain_health":
            health = brain.health()
            return {
                "content": [
                    {"type": "text", "text": json.dumps(health, ensure_ascii=False)}
                ]
            }

        elif tool_name == "brain_pipeline_stats":
            if hasattr(brain, "_learning_pipeline") and brain._learning_pipeline:
                stats = brain._learning_pipeline.stats()
            else:
                stats = {"error": "Learning pipeline not initialized"}
            return {
                "content": [
                    {"type": "text", "text": json.dumps(stats, ensure_ascii=False)}
                ]
            }

        elif tool_name == "brain_context_bracket":
            if hasattr(brain, "_learning_pipeline") and brain._learning_pipeline:
                tracker = brain._learning_pipeline._context_tracker
                if tracker:
                    bracket_info = {
                        "bracket": tracker.bracket.value,
                        "remaining_ratio": round(tracker.remaining_ratio, 4),
                        "tokens_used": tracker.tokens_used,
                        "should_handoff": tracker.should_handoff(),
                    }
                else:
                    bracket_info = {"bracket": "fresh", "remaining_ratio": 1.0}
            else:
                bracket_info = {"bracket": "fresh", "remaining_ratio": 1.0}
            return {
                "content": [
                    {"type": "text", "text": json.dumps(bracket_info, ensure_ascii=False)}
                ]
            }

        elif tool_name == "brain_route_suggest":
            task = arguments.get("task", "")
            if hasattr(brain, "_learning_pipeline") and brain._learning_pipeline:
                router = brain._learning_pipeline._router
                if router:
                    decision = router.route(task)
                    route_info = {
                        "suggested_agent": decision.agent,
                        "confidence": decision.confidence,
                        "exploiting": decision.exploiting,
                        "q_values": decision.q_values,
                    }
                else:
                    route_info = {"error": "Router not initialized"}
            else:
                route_info = {"error": "Learning pipeline not initialized"}
            return {
                "content": [
                    {"type": "text", "text": json.dumps(route_info, ensure_ascii=False)}
                ]
            }

        elif tool_name == "brain_capabilities":
            try:
                from ._brain_manifest import _sdk_capabilities
                caps = _sdk_capabilities()
            except ImportError:
                caps = {"error": "Manifest module not available"}
            return {
                "content": [
                    {"type": "text", "text": json.dumps(caps, ensure_ascii=False)}
                ]
            }

        elif tool_name == "brain_benchmark":
            try:
                import dataclasses

                from .contrib.enhancements.eval_benchmark import run_standard_benchmark
                result = run_standard_benchmark()
                result_dict = dataclasses.asdict(result)
                # Remove individual case details for MCP response size
                result_dict.pop("cases", None)
                return {
                    "content": [
                        {"type": "text", "text": json.dumps(result_dict, ensure_ascii=False)}
                    ]
                }
            except ImportError:
                return {
                    "content": [
                        {"type": "text", "text": json.dumps({"error": "Benchmark not available"}, ensure_ascii=False)}
                    ]
                }

        elif tool_name == "brain_briefing":
            try:
                md = brain.briefing()
                return {
                    "content": [
                        {"type": "text", "text": md}
                    ]
                }
            except Exception as exc:
                return {"error": str(exc)}

        else:
            return {"error": f"Unknown tool: {tool_name}"}

    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# MCP request handlers
# ---------------------------------------------------------------------------


def _handle_initialize(req_id: Any) -> dict[str, Any]:
    """Respond to the MCP initialize handshake."""
    return _ok(
        req_id,
        {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {
                "tools": {"listChanged": False},
            },
            "serverInfo": {
                "name": SERVER_NAME,
                "version": SERVER_VERSION,
            },
        },
    )


def _handle_tools_list(req_id: Any) -> dict[str, Any]:
    """Return all exposed tool schemas."""
    return _ok(req_id, {"tools": _TOOL_SCHEMAS})


def _handle_tools_call(
    req_id: Any, params: dict[str, Any], brain: Any
) -> dict[str, Any]:
    """Dispatch a tool call and wrap the result."""
    tool_name = params.get("name", "")
    arguments = params.get("arguments") or {}
    if not isinstance(arguments, dict):
        return _err(req_id, INVALID_PARAMS, "arguments must be an object")

    result = _dispatch(brain, tool_name, arguments)
    if "error" in result and "content" not in result:
        # Tool-level error — still a successful RPC, but isError=true per MCP spec
        return _ok(
            req_id,
            {
                "content": [{"type": "text", "text": result["error"]}],
                "isError": True,
            },
        )
    return _ok(req_id, result)


def _handle_ping(req_id: Any) -> dict[str, Any]:
    """Respond to ping."""
    return _ok(req_id, {})


# ---------------------------------------------------------------------------
# Server loop
# ---------------------------------------------------------------------------


def run_server(brain_dir: str | Path | None, *, stdin=None, stdout=None) -> None:
    """Run the MCP stdio server until the client sends shutdown or EOF.

    Args:
        brain_dir: Path to the brain directory. If None the server starts
                   without a brain and returns errors for tool calls.
        stdin: Readable binary stream (defaults to sys.stdin.buffer).
        stdout: Writable binary stream (defaults to sys.stdout.buffer).
    """
    in_stream: io.RawIOBase = stdin or sys.stdin.buffer  # type: ignore[assignment]
    out_stream: io.RawIOBase = stdout or sys.stdout.buffer  # type: ignore[assignment]

    # Auto-detect brain dir if not provided
    if brain_dir is None:
        import os
        brain_dir = os.environ.get("BRAIN_DIR")
        if brain_dir is None:
            # Default: ~/.gradata/brain
            brain_dir = str(Path.home() / ".gradata" / "brain")

    # Instantiate Brain from the module-level import (patchable in tests).
    # Auto-initialize if the directory doesn't exist (zero-friction first run).
    brain: Any = None
    if brain_dir is not None:
        try:
            if Brain is None:
                raise ImportError("gradata.brain.Brain could not be imported")
            brain_path = Path(brain_dir)
            if not brain_path.exists():
                _log.info("Auto-initializing brain at %s", brain_dir)
                brain = Brain.init(brain_dir, domain="General")
            else:
                brain = Brain(brain_dir)
        except Exception as exc:
            # Log to stderr so it does not pollute the JSON-RPC channel
            _log.error("Brain init failed: %s", exc)

    while True:
        msg = _read_message(in_stream)
        if msg is None:
            break  # EOF — client disconnected

        method: str = msg.get("method", "")
        req_id: Any = msg.get("id")  # None for notifications
        params: dict[str, Any] = msg.get("params") or {}

        # Notifications have no id and require no response
        is_notification = req_id is None

        if method == "initialize":
            response = _handle_initialize(req_id)

        elif method == "notifications/initialized":
            # Acknowledge-only notification; no response required
            continue

        elif method == "ping":
            response = _handle_ping(req_id)

        elif method == "tools/list":
            response = _handle_tools_list(req_id)

        elif method == "tools/call":
            response = _handle_tools_call(req_id, params, brain)

        elif method == "shutdown":
            if not is_notification:
                _write_message(out_stream, _ok(req_id, None))
            break

        elif is_notification:
            # Unknown notification — silently ignore per JSON-RPC spec
            continue

        else:
            response = _err(req_id, METHOD_NOT_FOUND, f"Method not found: {method}")

        _write_message(out_stream, response)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Parse CLI args and start the stdio MCP server."""
    parser = argparse.ArgumentParser(
        prog="gradata.mcp_server",
        description="Gradata MCP server (JSON-RPC 2.0 over stdio)",
    )
    parser.add_argument(
        "--brain-dir",
        metavar="PATH",
        help="Path to the brain directory (default: $BRAIN_DIR env var)",
    )
    args = parser.parse_args()

    brain_dir: str | None = args.brain_dir
    if brain_dir is None:
        import os

        brain_dir = os.environ.get("BRAIN_DIR")

    run_server(brain_dir)


if __name__ == "__main__":
    main()
