"""Tests for platform source auto-detection and event enrichment.

Verifies:
- `detect_platform_source()` returns expected labels for each env combo.
- `_events.emit()` attaches the detected tag to every event's data dict.
- Explicit override via GRADATA_PLATFORM_SOURCE is respected.
- Enrichment does not collide with future `applies_to`-style scope metadata
  that PR #57 will add on top of the same `data` dict.
"""

from __future__ import annotations

import pytest

from gradata._platform import detect_platform_source

# ---------------------------------------------------------------------------
# detect_platform_source — unit tests via env monkeypatch
# ---------------------------------------------------------------------------

# Every platform-signalling env var we know about. Cleared before each test so
# the ambient CI/dev environment doesn't contaminate results.
_ALL_PLATFORM_ENV_VARS = (
    "GRADATA_PLATFORM_SOURCE",
    "CLAUDECODE",
    "CLAUDE_CODE",
    "CURSOR",
    "CURSOR_TRACE_ID",
    "WINDSURF",
    "WINDSURF_SESSION_ID",
    "GRADATA_MCP_SERVER",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
)


@pytest.fixture(autouse=True)
def _clean_platform_env(monkeypatch):
    for var in _ALL_PLATFORM_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    yield


def test_default_fallback_is_raw_python():
    assert detect_platform_source() == "raw-python"


def test_claude_code_detected(monkeypatch):
    monkeypatch.setenv("CLAUDECODE", "1")
    assert detect_platform_source() == "claude-code"


def test_cursor_detected(monkeypatch):
    monkeypatch.setenv("CURSOR_TRACE_ID", "abc")
    assert detect_platform_source() == "cursor"


def test_windsurf_detected(monkeypatch):
    monkeypatch.setenv("WINDSURF", "1")
    assert detect_platform_source() == "windsurf"


def test_mcp_server_detected(monkeypatch):
    monkeypatch.setenv("GRADATA_MCP_SERVER", "1")
    assert detect_platform_source() == "mcp-server"


def test_anthropic_sdk_detected_when_no_ide(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert detect_platform_source() == "anthropic-sdk"


def test_openai_sdk_detected_when_no_ide(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert detect_platform_source() == "openai-sdk"


def test_ide_beats_sdk(monkeypatch):
    """If CLAUDECODE and ANTHROPIC_API_KEY are both set, CLAUDECODE wins."""
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert detect_platform_source() == "claude-code"


def test_explicit_override_wins(monkeypatch):
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("GRADATA_PLATFORM_SOURCE", "my-custom-host")
    assert detect_platform_source() == "my-custom-host"


def test_empty_override_falls_back(monkeypatch):
    monkeypatch.setenv("GRADATA_PLATFORM_SOURCE", "   ")
    assert detect_platform_source() == "raw-python"


# ---------------------------------------------------------------------------
# _events.emit — integration: platform_source rides along on the data dict
# ---------------------------------------------------------------------------


def test_emit_attaches_platform_source(fresh_brain, monkeypatch):
    monkeypatch.setenv("CLAUDECODE", "1")
    event = fresh_brain.emit("TEST_EVENT", "pytest", data={"foo": "bar"})
    assert event["data"]["platform_source"] == "claude-code"
    assert event["data"]["foo"] == "bar"  # caller data preserved


def test_emit_attaches_platform_source_when_data_none(fresh_brain, monkeypatch):
    monkeypatch.setenv("CURSOR", "1")
    event = fresh_brain.emit("TEST_EVENT", "pytest")
    assert event["data"]["platform_source"] == "cursor"


def test_emit_caller_can_override_platform_source(fresh_brain, monkeypatch):
    """Callers (e.g. replay / backfill tools) can set platform_source explicitly."""
    monkeypatch.setenv("CLAUDECODE", "1")
    event = fresh_brain.emit(
        "TEST_EVENT", "pytest", data={"platform_source": "backfill"},
    )
    assert event["data"]["platform_source"] == "backfill"


def test_emit_platform_source_is_raw_python_when_no_env(fresh_brain):
    # Autouse fixture already stripped platform env vars.
    event = fresh_brain.emit("TEST_EVENT", "pytest")
    assert event["data"]["platform_source"] == "raw-python"


def test_does_not_mutate_caller_data_dict(fresh_brain, monkeypatch):
    """emit() must not add platform_source to the caller's dict in place."""
    monkeypatch.setenv("CLAUDECODE", "1")
    caller_data = {"foo": "bar"}
    fresh_brain.emit("TEST_EVENT", "pytest", data=caller_data)
    assert "platform_source" not in caller_data, "emit mutated caller's dict"


def test_platform_source_coexists_with_scope_metadata(fresh_brain, monkeypatch):
    """Simulates PR #57's applies_to riding on the same data dict.

    Platform enrichment must not stomp on arbitrary scope/binding tokens a
    caller has already attached (e.g. scope-tagging work).
    """
    monkeypatch.setenv("CLAUDECODE", "1")
    event = fresh_brain.emit(
        "CORRECTION", "brain.correct",
        data={"applies_to": "scope:feature-xyz", "severity": "minor"},
    )
    assert event["data"]["platform_source"] == "claude-code"
    assert event["data"]["applies_to"] == "scope:feature-xyz"
    assert event["data"]["severity"] == "minor"
