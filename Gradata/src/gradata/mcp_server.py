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
import contextlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING, Any

from gradata.exceptions import BrainLockedError

if TYPE_CHECKING:
    import io

# Import Brain at module level so tests can patch gradata.mcp_server.Brain.
# The import is guarded so the module stays usable even if the brain package
# has missing optional dependencies at collection time.
try:
    from gradata.brain import Brain
except Exception:
    Brain = None  # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SERVER_NAME = "gradata"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2024-11-05"

# How long to wait on the daemon for a single tool call. MCP clients
# already have their own timeouts; keep this generous so slow brain
# operations (search, benchmark) don't get cut off.
_DAEMON_RPC_TIMEOUT = 60.0
_DAEMON_PROBE_TIMEOUT = 1.0


# ---------------------------------------------------------------------------
# Daemon bridge — when a local gradata daemon is running, the MCP stdio
# server delegates tool calls over HTTP instead of opening the brain itself.
# That keeps a single process (the daemon) as the sole flock holder.
# ---------------------------------------------------------------------------


class _DaemonClient:
    """Thin HTTP client for the local gradata daemon's /mcp/* endpoints."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    @classmethod
    def discover(cls, brain_dir: Path | None) -> _DaemonClient | None:
        """Locate a running daemon for *brain_dir*; return a client or None.

        Discovery order:
            1. $GRADATA_DAEMON_URL env var (full base URL, e.g. http://127.0.0.1:8765)
            2. $GRADATA_DAEMON_PORT env var on 127.0.0.1
            3. <brain_dir>/.daemon.json written by daemon.start()
            4. The conventional 127.0.0.1:8765 port (legacy / dashboard default)

        Returns a client only if /health responds OK within _DAEMON_PROBE_TIMEOUT.
        """
        import os

        candidates: list[str] = []

        env_url = os.environ.get("GRADATA_DAEMON_URL")
        if env_url:
            candidates.append(env_url)

        env_port = os.environ.get("GRADATA_DAEMON_PORT")
        if env_port and env_port.isdigit():
            candidates.append(f"http://127.0.0.1:{env_port}")

        if brain_dir is not None:
            advert = Path(brain_dir) / ".daemon.json"
            if advert.exists():
                try:
                    info = json.loads(advert.read_text(encoding="utf-8"))
                    port = int(info.get("port", 0))
                    if port:
                        candidates.append(f"http://127.0.0.1:{port}")
                except (OSError, ValueError, json.JSONDecodeError):
                    pass

        # Last-resort: the documented HTTP-daemon port. Lets the bridge
        # find an existing daemon even if .daemon.json hasn't been written
        # yet (older daemon, fresh install, etc.).
        candidates.append("http://127.0.0.1:8765")

        seen: set[str] = set()
        for url in candidates:
            url = url.rstrip("/")
            if url in seen:
                continue
            seen.add(url)
            if cls._probe(url):
                _log.info("MCP bridge: connected to gradata daemon at %s", url)
                return cls(url)
        return None

    @staticmethod
    def _probe(base_url: str) -> bool:
        try:
            req = urllib.request.Request(f"{base_url}/health", method="GET")
            with urllib.request.urlopen(req, timeout=_DAEMON_PROBE_TIMEOUT) as resp:
                return 200 <= resp.status < 300
        except (urllib.error.URLError, OSError, ValueError):
            return False

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """POST a tool call to the daemon's /mcp/tool-call endpoint."""
        payload = json.dumps({"name": tool_name, "arguments": arguments}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/mcp/tool-call",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=_DAEMON_RPC_TIMEOUT) as resp:
                body = resp.read()
        except urllib.error.HTTPError as exc:
            # Daemon answered with a non-2xx — treat as a tool-level error.
            try:
                body = exc.read()
                data = json.loads(body.decode("utf-8"))
            except Exception:
                data = {"error": f"daemon HTTP {exc.code}: {exc.reason}"}
            return data if isinstance(data, dict) else {"error": str(data)}
        except (urllib.error.URLError, OSError) as exc:
            return {"error": f"daemon unreachable: {exc}"}

        try:
            data = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            return {"error": f"daemon returned invalid JSON: {exc}"}
        return data if isinstance(data, dict) else {"error": "daemon returned non-object"}


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
        "name": "gradata_recall",
        "description": (
            "Retrieve relevant Gradata brain rules for the current situation under a token budget. "
            "WHEN: Call before tool use or drafting when you need compact behavioral memory injection. "
            "RETURNS: <brain-rules> XML text."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "situation": {"type": "string", "description": "Free-form current situation"},
                "max_tokens": {
                    "type": "integer",
                    "description": "Approximate token budget (default from BrainConfig)",
                },
                "ranker": {
                    "type": "string",
                    "enum": ["hybrid", "flat", "tree_only"],
                },
                "include_all_sources": {
                    "type": "boolean",
                    "description": "Debug: include non-injectable meta-rule sources",
                    "default": False,
                },
            },
            "required": ["situation"],
        },
    },
    {
        "name": "brain_search",
        "description": (
            "Search the brain for relevant rules, patterns, and past corrections. "
            "WHEN: Use BEFORE drafting emails, code, or docs to ground output in learned style and prior fixes. "
            "Prefer this over brain_briefing for targeted lookups. "
            "RETURNS: {hits: [{score, scope, text, confidence, state}]}. "
            "EXAMPLE: brain_search({query: 'cold email tone for CTOs', top_k: 5})."
        ),
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
        "description": (
            "Log a correction where the user edited an AI draft into a final version. "
            "WHEN: Call immediately after the user rewrites or revises AI output — this is the PRIMARY learning signal. "
            "Edit distance and severity drive confidence graduation (INSTINCT→PATTERN→RULE). "
            "RETURNS: {severity, edit_distance, category, event_id}. "
            "EXAMPLE: brain_correct({draft: 'Hi John,', final: 'Hey John —'})."
        ),
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
        "description": (
            "Log an AI-generated output (no correction yet) for quality tracking and trend analysis. "
            "WHEN: Fire-and-forget after producing output the user hasn't edited — paired with brain_correct later if they do edit. "
            "Use output_type to bucket (email, code, research, outreach). "
            "RETURNS: {event_id, tracked: bool}. "
            "EXAMPLE: brain_log_output({text: '...draft...', output_type: 'email', self_score: 7})."
        ),
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
        "description": (
            "Generate the brain quality manifest: rule counts by tier, confidence distribution, graduation stats. "
            "WHEN: Weekly/monthly audit of brain health. Use brain_health for a ready-made verdict instead. "
            "RETURNS: markdown string with counts, graduated rules, top categories. "
            "EXAMPLE: brain_manifest()."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "brain_health",
        "description": (
            "Return a human-readable brain health verdict with pass/warn/fail per subsystem. "
            "WHEN: Session-start diagnostic or when brain behaviour feels off. Prefer over brain_manifest for quick reads. "
            "RETURNS: markdown report with events count, corruption checks, graduation velocity, schema drift. "
            "EXAMPLE: brain_health()."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "brain_pipeline_stats",
        "description": (
            "Return procedural memory pipeline internals: stage throughputs, router Q-values, cluster counts. "
            "WHEN: Performance debugging or tuning graduation thresholds. Developer-facing, not day-to-day. "
            "RETURNS: {stages, router, context_bracket, clusters}. "
            "EXAMPLE: brain_pipeline_stats()."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "brain_context_bracket",
        "description": (
            "Get current context-degradation bracket: FRESH / MODERATE / DEEP / CRITICAL. "
            "WHEN: Call before long tool chains or multi-step work to decide whether to compact/reset. "
            "CRITICAL means warn the user and suggest a fresh session. "
            "RETURNS: {bracket, token_estimate, recommendation}. "
            "EXAMPLE: brain_context_bracket()."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "brain_route_suggest",
        "description": (
            "Suggest the best specialist agent for a task using the learned Q-Learning router. "
            "WHEN: Before spawning a subagent, to pick the right persona based on past outcome rewards. "
            "RETURNS: {agent, confidence, q_value, alternatives}. "
            "EXAMPLE: brain_route_suggest({task: 'review security of auth handler'})."
        ),
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
        "description": (
            "List active SDK capabilities and which modules back them (diff_engine, quality_gates, router, etc.). "
            "WHEN: Onboarding check — confirm the installed Gradata build has the features you're about to use. "
            "RETURNS: {capabilities: [{name, module, version, enabled}]}. "
            "EXAMPLE: brain_capabilities()."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "brain_benchmark",
        "description": (
            "Run the procedural-memory quality benchmark against the current brain. "
            "WHEN: CI/CD regression checks or after major rule ingestion. Slow — not for inline use. "
            "RETURNS: {score, pass_rate, regression_deltas, by_category}. "
            "EXAMPLE: brain_benchmark()."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "brain_briefing",
        "description": (
            "Generate a portable markdown briefing any AI agent can paste as context. "
            "WHEN: Session start (one-shot context dump) or when handing off to another tool/agent. "
            "Prefer brain_search for targeted lookups — briefings are comprehensive, not precise. "
            "RETURNS: markdown string with graduated rules, meta-rules, active patterns, voice notes. "
            "EXAMPLE: brain_briefing()."
        ),
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
        if tool_name == "gradata_recall":
            from gradata.mcp_tools import gradata_recall

            situation = arguments.get("situation", "")
            max_tokens_arg = arguments.get("max_tokens")
            ranker_arg = arguments.get("ranker")
            text = gradata_recall(
                str(situation),
                max_tokens=int(max_tokens_arg) if max_tokens_arg is not None else None,
                ranker=str(ranker_arg) if ranker_arg is not None else None,
                include_all_sources=bool(arguments.get("include_all_sources", False)),
                lessons_path=getattr(brain, "_find_lessons_path", lambda: None)(),
                meta_rules_path=Path(getattr(brain, "dir", ".")) / "meta-rules.json",
            )
            return {"content": [{"type": "text", "text": text}]}

        if tool_name == "brain_search":
            query = arguments.get("query", "")
            top_k = int(arguments.get("top_k", 5))
            results = brain.search(query, top_k=top_k)
            return {"content": [{"type": "text", "text": json.dumps(results, ensure_ascii=False)}]}

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
            return {"content": [{"type": "text", "text": json.dumps(summary, ensure_ascii=False)}]}

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
            return {"content": [{"type": "text", "text": json.dumps(safe, ensure_ascii=False)}]}

        elif tool_name == "brain_manifest":
            manifest = brain.manifest()
            return {"content": [{"type": "text", "text": json.dumps(manifest, ensure_ascii=False)}]}

        elif tool_name == "brain_health":
            health = brain.health()
            return {"content": [{"type": "text", "text": json.dumps(health, ensure_ascii=False)}]}

        elif tool_name == "brain_pipeline_stats":
            if hasattr(brain, "_learning_pipeline") and brain._learning_pipeline:
                stats = brain._learning_pipeline.stats()
            else:
                stats = {"error": "Learning pipeline not initialized"}
            return {"content": [{"type": "text", "text": json.dumps(stats, ensure_ascii=False)}]}

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
                "content": [{"type": "text", "text": json.dumps(bracket_info, ensure_ascii=False)}]
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
                "content": [{"type": "text", "text": json.dumps(route_info, ensure_ascii=False)}]
            }

        elif tool_name == "brain_capabilities":
            try:
                from gradata._brain_manifest import _sdk_capabilities

                caps = _sdk_capabilities()
            except ImportError:
                caps = {"error": "Manifest module not available"}
            return {"content": [{"type": "text", "text": json.dumps(caps, ensure_ascii=False)}]}

        elif tool_name == "brain_benchmark":
            try:
                import dataclasses

                from gradata.contrib.enhancements.eval_benchmark import run_standard_benchmark

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
                        {
                            "type": "text",
                            "text": json.dumps(
                                {"error": "Benchmark not available"}, ensure_ascii=False
                            ),
                        }
                    ]
                }

        elif tool_name == "brain_briefing":
            try:
                md = brain.briefing()
                return {"content": [{"type": "text", "text": md}]}
            except Exception as exc:
                return {"error": str(exc)}

        else:
            return {"error": f"Unknown tool: {tool_name}"}

    except Exception as exc:
        # Log with traceback so production failures are diagnosable.
        _log.exception("_dispatch failed for tool=%s", tool_name)
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
    req_id: Any,
    params: dict[str, Any],
    brain: Any,
    daemon_client: _DaemonClient | None = None,
) -> dict[str, Any]:
    """Dispatch a tool call and wrap the result.

    When *daemon_client* is provided, the tool call is forwarded to the
    running daemon over HTTP (no local Brain access). Otherwise it falls
    back to dispatching against the in-process *brain*.
    """
    tool_name = params.get("name", "")
    arguments = params.get("arguments") or {}
    if not isinstance(arguments, dict):
        return _err(req_id, INVALID_PARAMS, "arguments must be an object")

    if daemon_client is not None:
        result = daemon_client.call_tool(tool_name, arguments)
    else:
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


def run_server(
    brain_dir: str | Path | None,
    *,
    stdin=None,
    stdout=None,
    daemon_client: _DaemonClient | None = None,
    use_daemon: bool = True,
) -> None:
    """Run the MCP stdio server until the client sends shutdown or EOF.

    Args:
        brain_dir: Path to the brain directory. If None the server starts
                   without a brain and returns errors for tool calls.
        stdin: Readable binary stream (defaults to sys.stdin.buffer).
        stdout: Writable binary stream (defaults to sys.stdout.buffer).
        daemon_client: Optional pre-built bridge client (mainly for tests).
        use_daemon: When True (default), try to bridge to a local daemon
                    over HTTP before falling back to opening the Brain in
                    this process. Set False to force the legacy in-process
                    behaviour (e.g. tests that mock Brain directly).
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

    brain_path = Path(brain_dir) if brain_dir is not None else None

    # Prefer the daemon-bridge transport: if a daemon is already running for
    # this brain, talk to it over HTTP and never grab the flock ourselves.
    if daemon_client is None and use_daemon:
        daemon_client = _DaemonClient.discover(brain_path)

    # Instantiate Brain from the module-level import (patchable in tests).
    # Auto-initialize if the directory doesn't exist (zero-friction first run).
    brain: Any = None
    lock_cm = None
    if daemon_client is None and brain_dir is not None:
        try:
            if Brain is None:
                raise ImportError("gradata.brain.Brain could not be imported")
            if brain_path is not None and not brain_path.exists():
                _log.info("Auto-initializing brain at %s", brain_dir)
                brain = Brain.init(brain_dir, domain="General")
            else:
                brain = Brain(brain_dir)
            from gradata._brain_lock import acquire_brain_lock

            lock_path = getattr(brain, "dir", brain_path)
            lock_cm = acquire_brain_lock(lock_path)
            lock_cm.__enter__()
        except Exception as exc:
            if lock_cm is not None:
                with contextlib.suppress(Exception):
                    lock_cm.__exit__(None, None, None)
            # Log to stderr so it does not pollute the JSON-RPC channel
            _log.error("Brain init failed: %s", exc)
            if isinstance(exc, BrainLockedError):
                raise
    try:
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
                response = _handle_tools_call(req_id, params, brain, daemon_client)

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
    finally:
        if lock_cm is not None:
            lock_cm.__exit__(None, None, None)


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
    parser.add_argument(
        "--no-daemon",
        action="store_true",
        help=(
            "Disable HTTP-bridge mode and always open the brain in-process. "
            "By default the server delegates tool calls to a local gradata "
            "daemon if one is running (recommended — avoids flock contention)."
        ),
    )
    args = parser.parse_args()

    brain_dir: str | None = args.brain_dir
    if brain_dir is None:
        import os

        brain_dir = os.environ.get("BRAIN_DIR")

    run_server(brain_dir, use_daemon=not args.no_daemon)


if __name__ == "__main__":
    main()
