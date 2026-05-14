"""
Tests for the MCP stdio ⇄ HTTP-daemon bridge.

Covers:
- `_DaemonClient.discover` finds the daemon via .daemon.json
- `_DaemonClient.discover` returns None when no daemon is reachable
- `run_server` in bridge mode does NOT open the Brain (no flock contention)
- New daemon endpoints /mcp/tools and /mcp/tool-call work end-to-end
"""

from __future__ import annotations

import io
import json
import threading
import urllib.request
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest

from gradata.daemon import GradataDaemon
from gradata.mcp_server import _DaemonClient, run_server

if TYPE_CHECKING:
    from pathlib import Path


def _frame(obj: dict[str, Any]) -> bytes:
    body = json.dumps(obj).encode("utf-8")
    return f"Content-Length: {len(body)}\r\n\r\n".encode() + body


def _read_all(buf: io.BytesIO) -> list[dict[str, Any]]:
    buf.seek(0)
    raw = buf.read()
    responses: list[dict[str, Any]] = []
    while raw:
        if b"Content-Length:" not in raw:
            break
        header_end = raw.find(b"\r\n\r\n")
        if header_end == -1:
            break
        headers = raw[:header_end].decode()
        cl = 0
        for line in headers.split("\r\n"):
            if line.lower().startswith("content-length:"):
                cl = int(line.split(":", 1)[1].strip())
        body_start = header_end + 4
        body = raw[body_start : body_start + cl]
        responses.append(json.loads(body))
        raw = raw[body_start + cl :]
    return responses


@pytest.fixture
def live_daemon(brain_dir: Path):
    """Spin up a real GradataDaemon in a thread, yield (daemon, base_url)."""
    d = GradataDaemon(brain_dir, port=0)
    d._try_bind(0)
    assert d._server is not None
    d._server._daemon = d  # type: ignore[attr-defined]
    port = d._server.server_address[1]
    d._port = port
    d._reset_idle_timer()

    # Mirror what start() writes so discovery via .daemon.json works.
    from datetime import UTC, datetime

    from gradata.daemon import _write_pid_file

    _write_pid_file(
        brain_dir / ".daemon.json",
        port,
        brain_dir,
        datetime.now(UTC).isoformat(),
    )

    t = threading.Thread(target=d._server.serve_forever, daemon=True)
    t.start()
    try:
        yield d, f"http://127.0.0.1:{port}"
    finally:
        d._server.shutdown()
        advert = brain_dir / ".daemon.json"
        if advert.exists():
            advert.unlink()


# ── _DaemonClient.discover ───────────────────────────────────────────────


def test_discover_returns_none_when_no_daemon(tmp_path: Path) -> None:
    """No .daemon.json and no listener — discovery must return None."""
    # We can't fully isolate from a stray 127.0.0.1:8765 listener on the host,
    # but the explicit env vars + missing advert file means probe sequence is:
    # only the legacy 8765 fallback. We'll skip if that happens to answer.
    with patch.dict("os.environ", {}, clear=False):
        for k in ("GRADATA_DAEMON_URL", "GRADATA_DAEMON_PORT"):
            __import__("os").environ.pop(k, None)
        client = _DaemonClient.discover(tmp_path / "no-such-brain")
    if client is not None and client.base_url.endswith(":8765"):
        pytest.skip("Host has a daemon listening on 8765; can't assert no-discovery")
    assert client is None


def test_discover_finds_daemon_via_advert_file(live_daemon, brain_dir: Path) -> None:
    """A daemon advertising itself in <brain>/.daemon.json must be discovered."""
    _d, base = live_daemon
    client = _DaemonClient.discover(brain_dir)
    assert client is not None
    # The brain-dir-advertised port should win over the 8765 fallback.
    assert client.base_url == base


# ── /mcp/tools and /mcp/tool-call endpoints ──────────────────────────────


def test_daemon_mcp_tools_endpoint_lists_schemas(live_daemon) -> None:
    _d, base = live_daemon
    with urllib.request.urlopen(f"{base}/mcp/tools", timeout=5) as resp:
        data = json.loads(resp.read())
    assert "tools" in data
    names = {t["name"] for t in data["tools"]}
    assert "brain_health" in names
    assert "brain_search" in names


def test_daemon_mcp_tool_call_endpoint_dispatches(live_daemon) -> None:
    _d, base = live_daemon
    payload = json.dumps({"name": "brain_health", "arguments": {}}).encode()
    req = urllib.request.Request(
        f"{base}/mcp/tool-call",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    # Either tool produces content or surfaces an error; both are dicts.
    assert isinstance(data, dict)
    assert "content" in data or "error" in data


# ── Bridge mode: run_server delegates and never opens Brain ──────────────


def test_run_server_in_bridge_mode_does_not_open_brain(live_daemon, brain_dir: Path) -> None:
    """When a daemon is discoverable, the stdio server must not instantiate Brain."""
    _d, _base = live_daemon

    in_buf = io.BytesIO(
        _frame({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        + _frame(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "brain_health", "arguments": {}},
            }
        )
        + _frame({"jsonrpc": "2.0", "id": 3, "method": "shutdown"})
    )
    out_buf = io.BytesIO()

    # If the bridge engages, gradata.mcp_server.Brain must not be invoked.
    with patch("gradata.mcp_server.Brain") as MockBrain:
        run_server(brain_dir, stdin=in_buf, stdout=out_buf)
        MockBrain.assert_not_called()

    responses = _read_all(out_buf)
    ids = [r.get("id") for r in responses]
    assert 1 in ids and 2 in ids
    call = next(r for r in responses if r.get("id") == 2)
    # Tool call should have produced an MCP-shaped result via the daemon.
    assert "result" in call
