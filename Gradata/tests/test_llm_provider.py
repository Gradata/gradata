"""Tests for the unified LLM provider abstraction (BYO-Key / BYO-CLI / Cloud-Paid).

These tests exercise the new CLIProvider, GradataCloudProvider, and the
``auto`` factory resolution path. They never hit the network.
"""

from __future__ import annotations

import io
import json
import urllib.error
from unittest.mock import patch

import pytest

from gradata.enhancements import llm_provider as lp


# ---------------------------------------------------------------------------
# CLIProvider
# ---------------------------------------------------------------------------


class _FakeProc:
    def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def test_cli_provider_claude_happy(monkeypatch):
    """When `claude` CLI is on PATH and returns 0, .complete() returns its stdout."""
    monkeypatch.setattr(lp.shutil, "which",
                        lambda name: "/usr/local/bin/claude" if name == "claude" else None)
    captured: dict = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        return _FakeProc(stdout="When drafting, lead with the benefit.\n", returncode=0)

    monkeypatch.setattr(lp.subprocess, "run", fake_run)
    provider = lp.CLIProvider(cli_name="claude")
    out = provider.complete("Synthesize this group of corrections.")
    assert out == "When drafting, lead with the benefit."
    assert captured["argv"][0] == "/usr/local/bin/claude"
    assert "-p" in captured["argv"]
    assert "--output-format" in captured["argv"]


def test_cli_provider_binary_missing(monkeypatch):
    """If shutil.which returns None for every CLI, .complete() degrades to None."""
    monkeypatch.setattr(lp.shutil, "which", lambda _name: None)
    monkeypatch.delenv("GRADATA_LLM_CLI", raising=False)
    provider = lp.CLIProvider()
    assert provider.cli_name is None
    assert provider.complete("hello") is None


def test_cli_provider_circuit_breaker(monkeypatch):
    """3 consecutive failures opens the circuit; the 4th call must skip subprocess."""
    monkeypatch.setattr(lp.shutil, "which",
                        lambda name: "/usr/local/bin/claude" if name == "claude" else None)
    call_count = {"n": 0}

    def fake_run(argv, **kwargs):
        call_count["n"] += 1
        return _FakeProc(stdout="", stderr="boom", returncode=1)

    monkeypatch.setattr(lp.subprocess, "run", fake_run)
    provider = lp.CLIProvider(cli_name="claude")
    # 3 failing calls
    for _ in range(3):
        assert provider.complete("x") is None
    assert call_count["n"] == 3
    # 4th call: circuit open, no subprocess
    assert provider.complete("x") is None
    assert call_count["n"] == 3


def test_cli_provider_codex_argv(monkeypatch):
    """Codex argv shape is the documented `codex exec ... -m <model> <prompt>`."""
    monkeypatch.setattr(lp.shutil, "which",
                        lambda name: "/usr/local/bin/codex" if name == "codex" else None)
    captured: dict = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        return _FakeProc(stdout="ok", returncode=0)

    monkeypatch.setattr(lp.subprocess, "run", fake_run)
    provider = lp.CLIProvider(cli_name="codex", model="gpt-5.5")
    assert provider.complete("hello") == "ok"
    assert "exec" in captured["argv"]
    assert "--sandbox" in captured["argv"]
    assert "read-only" in captured["argv"]
    assert "-m" in captured["argv"]
    assert "gpt-5.5" in captured["argv"]


# ---------------------------------------------------------------------------
# GradataCloudProvider
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_cloud_provider_happy(monkeypatch):
    """Cloud provider POSTs the right shape and parses {text: ...}."""
    captured: dict = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["headers"] = dict(req.headers)
        captured["body"] = json.loads(req.data.decode())
        return _FakeResponse(json.dumps({"text": "Synthesized principle."}).encode())

    monkeypatch.setattr(lp.urllib.request, "urlopen", fake_urlopen)
    provider = lp.GradataCloudProvider(api_key="sk-test", endpoint="https://api.gradata.cloud")
    out = provider.complete("test prompt", max_tokens=300)
    assert out == "Synthesized principle."
    assert captured["url"].endswith("/meta-rules/synthesize")
    # Headers are normalized to title-case by urllib
    assert captured["headers"].get("Authorization") == "Bearer sk-test"
    assert captured["body"]["prompt"] == "test prompt"
    assert captured["body"]["max_tokens"] == 300


def test_cloud_provider_402(monkeypatch):
    """402 Payment Required → graceful None (quota exhausted)."""
    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 402, "Payment Required", {}, io.BytesIO(b""))

    monkeypatch.setattr(lp.urllib.request, "urlopen", fake_urlopen)
    provider = lp.GradataCloudProvider(api_key="sk-test", endpoint="https://api.gradata.cloud")
    assert provider.complete("test") is None


def test_cloud_provider_no_key(monkeypatch):
    """Missing GRADATA_API_KEY → returns None without making a request."""
    monkeypatch.delenv("GRADATA_API_KEY", raising=False)
    called = {"n": 0}
    def fake_urlopen(*a, **kw):
        called["n"] += 1
        raise AssertionError("must not be called")
    monkeypatch.setattr(lp.urllib.request, "urlopen", fake_urlopen)
    provider = lp.GradataCloudProvider(api_key="", endpoint="https://api.gradata.cloud")
    assert provider.complete("x") is None
    assert called["n"] == 0


# ---------------------------------------------------------------------------
# Factory auto-resolution
# ---------------------------------------------------------------------------


def test_factory_auto_resolution(monkeypatch):
    """auto picks cli when claude present; anthropic when only ANTHROPIC_API_KEY set;
    cloud when only GRADATA_API_KEY set; None when nothing configured."""
    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GRADATA_LLM_KEY",
                "GRADATA_API_KEY", "GRADATA_GEMMA_API_KEY", "GRADATA_LLM_PROVIDER"):
        monkeypatch.delenv(var, raising=False)

    # Case 1: claude on PATH → CLIProvider
    monkeypatch.setattr(lp.shutil, "which",
                        lambda name: "/u/claude" if name == "claude" else None)
    p = lp.get_provider("auto")
    assert isinstance(p, lp.CLIProvider)

    # Case 2: nothing on PATH but ANTHROPIC_API_KEY → AnthropicProvider
    monkeypatch.setattr(lp.shutil, "which", lambda _name: None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    p = lp.get_provider("auto")
    assert isinstance(p, lp.AnthropicProvider)
    monkeypatch.delenv("ANTHROPIC_API_KEY")

    # Case 3: only GRADATA_API_KEY → GradataCloudProvider
    monkeypatch.setenv("GRADATA_API_KEY", "sk-cloud")
    p = lp.get_provider("auto")
    assert isinstance(p, lp.GradataCloudProvider)
    monkeypatch.delenv("GRADATA_API_KEY")

    # Case 4: nothing configured → None
    p = lp.get_provider("auto")
    assert p is None


def test_factory_unknown_provider_raises():
    with pytest.raises(ValueError):
        lp.get_provider("xyz-not-a-real-provider")
