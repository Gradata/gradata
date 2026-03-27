"""
Tests for gradata.mcp_server — JSON-RPC 2.0 stdio MCP transport.

Run:
    cd sdk && python -m pytest tests/test_mcp_server.py -v
"""

from __future__ import annotations

import io
import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers — import the module under test
# ---------------------------------------------------------------------------

from gradata.mcp_server import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    METHOD_NOT_FOUND,
    _TOOL_SCHEMAS,
    _dispatch,
    _err,
    _handle_initialize,
    _handle_ping,
    _handle_tools_call,
    _handle_tools_list,
    _ok,
    _read_message,
    _write_message,
    run_server,
)


# ---------------------------------------------------------------------------
# Framing helpers
# ---------------------------------------------------------------------------

def _frame(obj: dict[str, Any]) -> bytes:
    """Encode a dict as a Content-Length-framed JSON-RPC message."""
    body = json.dumps(obj).encode("utf-8")
    return f"Content-Length: {len(body)}\r\n\r\n".encode() + body


def _make_stream(*messages: dict[str, Any]) -> io.BytesIO:
    """Return a BytesIO stream pre-loaded with framed messages."""
    return io.BytesIO(b"".join(_frame(m) for m in messages))


def _read_all_responses(buf: io.BytesIO) -> list[dict[str, Any]]:
    """Read all framed JSON-RPC responses written into a BytesIO buffer."""
    buf.seek(0)
    responses: list[dict[str, Any]] = []
    raw = buf.read()
    # Split on the header boundary and parse each chunk
    while raw:
        if b"Content-Length:" not in raw:
            break
        header_end = raw.find(b"\r\n\r\n")
        if header_end == -1:
            break
        header = raw[: header_end + 4]
        length = int(
            next(
                line.split(b":")[1].strip()
                for line in header.split(b"\r\n")
                if b"Content-Length" in line
            )
        )
        body_start = header_end + 4
        body = raw[body_start : body_start + length]
        responses.append(json.loads(body))
        raw = raw[body_start + length :]
    return responses


# ===========================================================================
# 1. Message framing — _read_message and _write_message
# ===========================================================================


class TestMessageFraming:
    """Tests for Content-Length framing helpers."""

    def test_read_message_parses_valid_frame(self):
        payload = {"jsonrpc": "2.0", "method": "ping", "id": 1}
        stream = io.BytesIO(_frame(payload))
        result = _read_message(stream)
        assert result == payload

    def test_read_message_returns_none_on_eof(self):
        stream = io.BytesIO(b"")
        assert _read_message(stream) is None

    def test_read_message_returns_none_on_corrupt_body(self):
        # Valid header, corrupt JSON body
        corrupt = b"Content-Length: 10\r\n\r\nnot_json!!"
        stream = io.BytesIO(corrupt)
        result = _read_message(stream)
        assert result is None

    def test_write_then_read_roundtrip(self):
        payload = {"jsonrpc": "2.0", "id": 99, "result": {"ok": True}}
        buf = io.BytesIO()
        _write_message(buf, payload)
        buf.seek(0)
        recovered = _read_message(buf)
        assert recovered == payload

    def test_write_message_sets_correct_content_length(self):
        payload = {"hello": "world"}
        buf = io.BytesIO()
        _write_message(buf, payload)
        buf.seek(0)
        raw = buf.read()
        header_end = raw.index(b"\r\n\r\n")
        header = raw[:header_end].decode()
        length_str = next(
            line.split(":")[1].strip()
            for line in header.split("\r\n")
            if "Content-Length" in line
        )
        actual_body = raw[header_end + 4 :]
        assert int(length_str) == len(actual_body)


# ===========================================================================
# 2. JSON-RPC helpers — _ok and _err
# ===========================================================================


class TestJsonRpcHelpers:
    """Tests for response builder utilities."""

    def test_ok_includes_jsonrpc_version(self):
        resp = _ok(1, {"x": 1})
        assert resp["jsonrpc"] == "2.0"

    def test_ok_includes_id_and_result(self):
        resp = _ok(42, {"answer": 42})
        assert resp["id"] == 42
        assert resp["result"] == {"answer": 42}

    def test_err_includes_error_code_and_message(self):
        resp = _err(3, METHOD_NOT_FOUND, "no such method")
        assert resp["error"]["code"] == METHOD_NOT_FOUND
        assert "no such method" in resp["error"]["message"]

    def test_err_includes_data_when_provided(self):
        resp = _err(1, INTERNAL_ERROR, "boom", data={"detail": "stack"})
        assert resp["error"]["data"] == {"detail": "stack"}

    def test_err_omits_data_key_when_none(self):
        resp = _err(1, INTERNAL_ERROR, "boom")
        assert "data" not in resp["error"]


# ===========================================================================
# 3. Individual handlers
# ===========================================================================


class TestHandlers:
    """Tests for handle_initialize, handle_ping, handle_tools_list."""

    def test_initialize_returns_protocol_version(self):
        resp = _handle_initialize(1)
        assert "protocolVersion" in resp["result"]

    def test_initialize_returns_server_info(self):
        resp = _handle_initialize(1)
        info = resp["result"]["serverInfo"]
        assert info["name"] == "gradata"
        assert "version" in info

    def test_initialize_advertises_tools_capability(self):
        resp = _handle_initialize(1)
        assert "tools" in resp["result"]["capabilities"]

    def test_ping_returns_empty_result(self):
        resp = _handle_ping(7)
        assert resp["result"] == {}
        assert resp["id"] == 7

    def test_tools_list_returns_five_tools(self):
        resp = _handle_tools_list(2)
        tools = resp["result"]["tools"]
        assert len(tools) == 5

    def test_tools_list_tool_names(self):
        resp = _handle_tools_list(2)
        names = {t["name"] for t in resp["result"]["tools"]}
        expected = {
            "brain_search",
            "brain_correct",
            "brain_log_output",
            "brain_manifest",
            "brain_health",
        }
        assert names == expected

    def test_tools_list_each_tool_has_input_schema(self):
        resp = _handle_tools_list(2)
        for tool in resp["result"]["tools"]:
            assert "inputSchema" in tool, f"Tool {tool['name']} missing inputSchema"


# ===========================================================================
# 4. Tool dispatch (_dispatch)
# ===========================================================================


class TestDispatch:
    """Tests for _dispatch — routing to brain methods."""

    def _make_brain(self, **overrides: Any) -> MagicMock:
        """Return a mock brain with sensible default return values."""
        brain = MagicMock()
        brain.search.return_value = [{"source": "test.md", "text": "result", "score": 1.0}]
        brain.correct.return_value = {
            "ts": "2026-01-01",
            "type": "CORRECTION",
            "source": "brain.correct",
        }
        brain.log_output.return_value = {
            "ts": "2026-01-01",
            "type": "OUTPUT",
            "source": "brain.log_output",
        }
        brain.manifest.return_value = {"schema_version": "1.0.0"}
        brain.health.return_value = {"healthy": True}
        for attr, val in overrides.items():
            setattr(brain, attr, val)
        return brain

    def test_dispatch_none_brain_returns_error(self):
        result = _dispatch(None, "brain_search", {"query": "test"})
        assert "error" in result

    def test_dispatch_unknown_tool_returns_error(self):
        brain = self._make_brain()
        result = _dispatch(brain, "does_not_exist", {})
        assert "error" in result
        assert "Unknown tool" in result["error"]

    def test_dispatch_brain_search_calls_search(self):
        brain = self._make_brain()
        result = _dispatch(brain, "brain_search", {"query": "hello", "top_k": 3})
        brain.search.assert_called_once_with("hello", top_k=3)
        assert "content" in result

    def test_dispatch_brain_search_default_top_k(self):
        brain = self._make_brain()
        _dispatch(brain, "brain_search", {"query": "q"})
        _, kwargs = brain.search.call_args
        assert kwargs["top_k"] == 5

    def test_dispatch_brain_correct_calls_correct(self):
        brain = self._make_brain()
        result = _dispatch(brain, "brain_correct", {"draft": "A", "final": "B"})
        brain.correct.assert_called_once_with("A", "B")
        assert "content" in result

    def test_dispatch_brain_log_output_calls_log_output(self):
        brain = self._make_brain()
        result = _dispatch(
            brain,
            "brain_log_output",
            {"text": "hello", "output_type": "email", "self_score": 8.5},
        )
        brain.log_output.assert_called_once_with(
            "hello", output_type="email", self_score=8.5
        )
        assert "content" in result

    def test_dispatch_brain_manifest_calls_manifest(self):
        brain = self._make_brain()
        result = _dispatch(brain, "brain_manifest", {})
        brain.manifest.assert_called_once()
        assert "content" in result

    def test_dispatch_brain_health_calls_health(self):
        brain = self._make_brain()
        result = _dispatch(brain, "brain_health", {})
        brain.health.assert_called_once()
        assert "content" in result

    def test_dispatch_exception_returns_error_not_raises(self):
        brain = self._make_brain()
        brain.search.side_effect = RuntimeError("db locked")
        result = _dispatch(brain, "brain_search", {"query": "x"})
        assert "error" in result
        assert "db locked" in result["error"]


# ===========================================================================
# 5. tools/call handler
# ===========================================================================


class TestHandleToolsCall:
    """Tests for the tools/call JSON-RPC handler."""

    def _make_brain(self) -> MagicMock:
        brain = MagicMock()
        brain.health.return_value = {"healthy": True}
        return brain

    def test_tools_call_bad_arguments_type_returns_error(self):
        resp = _handle_tools_call(1, {"name": "brain_health", "arguments": "bad"}, None)
        assert "error" in resp

    def test_tools_call_wraps_tool_error_as_is_error(self):
        # Dispatch returns an error dict — should produce isError=true result
        brain = MagicMock()
        brain.health.side_effect = RuntimeError("crash")
        resp = _handle_tools_call(1, {"name": "brain_health", "arguments": {}}, brain)
        assert resp["result"]["isError"] is True

    def test_tools_call_success_has_content(self):
        brain = self._make_brain()
        resp = _handle_tools_call(1, {"name": "brain_health", "arguments": {}}, brain)
        assert "content" in resp["result"]


# ===========================================================================
# 6. Full server lifecycle (run_server)
# ===========================================================================


class TestServerLifecycle:
    """End-to-end tests for run_server over in-memory streams."""

    def _run(self, *messages: dict[str, Any], brain_dir: Any = None) -> list[dict[str, Any]]:
        """Drive the server with *messages* and return all responses."""
        in_buf = _make_stream(*messages)
        out_buf = io.BytesIO()

        # Patch Brain so we never need a real directory
        mock_brain = MagicMock()
        mock_brain.search.return_value = []
        mock_brain.manifest.return_value = {"schema_version": "1.0.0"}
        mock_brain.health.return_value = {"healthy": True}
        mock_brain.correct.return_value = {"ts": "t", "type": "CORRECTION", "source": "s"}
        mock_brain.log_output.return_value = {"ts": "t", "type": "OUTPUT", "source": "s"}

        with patch("gradata.mcp_server.Brain", return_value=mock_brain):
            run_server(brain_dir or "/fake/brain", stdin=in_buf, stdout=out_buf)

        return _read_all_responses(out_buf)

    def test_initialize_response_has_protocol_version(self):
        responses = self._run({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        assert any("protocolVersion" in r.get("result", {}) for r in responses)

    def test_unknown_method_returns_method_not_found(self):
        responses = self._run(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "no_such_method", "params": {}},
        )
        errors = [r for r in responses if "error" in r]
        assert any(r["error"]["code"] == METHOD_NOT_FOUND for r in errors)

    def test_shutdown_terminates_loop(self):
        # Server should respond to shutdown and exit; no extra messages processed
        responses = self._run(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "shutdown"},
        )
        # We should get an initialize response and a shutdown null response
        ids = [r.get("id") for r in responses]
        assert 1 in ids
        assert 2 in ids

    def test_notifications_initialized_produces_no_response(self):
        responses = self._run(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            # This is a notification (no id) — server must not respond
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
        )
        ids = [r.get("id") for r in responses]
        assert None not in ids  # No response for the notification

    def test_tools_list_response_contains_tools(self):
        responses = self._run(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        )
        list_resp = next(r for r in responses if r.get("id") == 2)
        assert "tools" in list_resp["result"]

    def test_tools_call_brain_health_succeeds(self):
        responses = self._run(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "brain_health", "arguments": {}},
            },
        )
        call_resp = next(r for r in responses if r.get("id") == 3)
        assert "content" in call_resp["result"]

    def test_ping_is_handled(self):
        responses = self._run(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 5, "method": "ping", "params": {}},
        )
        ping_resp = next(r for r in responses if r.get("id") == 5)
        assert ping_resp["result"] == {}

    def test_no_brain_dir_returns_error_on_tool_call(self):
        """When brain_dir is None, tool calls must not crash the server."""
        in_buf = _make_stream(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "brain_health", "arguments": {}},
            },
        )
        out_buf = io.BytesIO()
        # Do NOT patch Brain — with brain_dir=None it won't try to instantiate
        run_server(None, stdin=in_buf, stdout=out_buf)
        responses = _read_all_responses(out_buf)
        call_resp = next(r for r in responses if r.get("id") == 2)
        # isError=true or the result content contains the error string
        result = call_resp["result"]
        assert result.get("isError") is True or "content" in result
