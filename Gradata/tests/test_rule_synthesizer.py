"""Fail-safe contracts for the SDK-only rule synthesizer.

The module must never raise — every failure path returns None so the
injection hook falls back to the fragmented format. These tests lock in
the public contract every OSS user will exercise on day one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gradata.enhancements import rule_synthesizer as rs


def test_no_api_key_returns_none(tmp_path, monkeypatch):
    """No API key → must return None, not raise."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    result = rs.synthesize_rules_block(
        brain_dir=tmp_path,
        mandatory_lines=["[MANDATORY] Never ship without tests."],
        cluster_lines=[],
        individual_lines=[],
    )
    assert result is None


def test_empty_inputs_returns_none(tmp_path, monkeypatch):
    """All-empty inputs must short-circuit before touching any provider."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-should-not-be-called")

    import sys as _sys
    import types as _types

    def _boom(*_a, **_kw):  # pragma: no cover - should never execute
        raise AssertionError("SDK must not be called on empty input")

    fake_mod = _types.ModuleType("anthropic")

    class _NeverCalled:
        def __init__(self, *a, **kw):
            _boom()

    fake_mod.Anthropic = _NeverCalled
    monkeypatch.setitem(_sys.modules, "anthropic", fake_mod)

    result = rs.synthesize_rules_block(
        brain_dir=tmp_path,
        mandatory_lines=[],
        cluster_lines=[],
        individual_lines=[],
        meta_block="",
    )
    assert result is None


def test_cache_hit_skips_provider(tmp_path, monkeypatch):
    """Cached block must be returned without calling the SDK."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    mandatory = ["[MANDATORY] Never paste raw URLs."]
    key = rs._compute_cache_key(mandatory, [], [], "", "", "", rs.DEFAULT_MODEL)
    cache_file = rs._cache_path(tmp_path, key)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(
        "<brain-wisdom>cached content payload ok ok ok</brain-wisdom>", encoding="utf-8"
    )

    result = rs.synthesize_rules_block(
        brain_dir=tmp_path,
        mandatory_lines=mandatory,
        cluster_lines=[],
        individual_lines=[],
    )
    assert result is not None
    assert "cached content" in result


def test_sdk_failure_returns_none(tmp_path, monkeypatch):
    """SDK raises with key present → must return None, not propagate."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")

    import sys as _sys
    import types as _types

    class _BrokenSDK:
        def __init__(self, *a, **kw):
            raise RuntimeError("anthropic SDK unavailable")

    fake_mod = _types.ModuleType("anthropic")
    fake_mod.Anthropic = _BrokenSDK
    monkeypatch.setitem(_sys.modules, "anthropic", fake_mod)

    result = rs.synthesize_rules_block(
        brain_dir=tmp_path,
        mandatory_lines=["[MANDATORY] test"],
        cluster_lines=[],
        individual_lines=[],
    )
    assert result is None


def test_malformed_output_returns_none(tmp_path, monkeypatch):
    """Missing <brain-wisdom> tags → None, no cache write."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")

    import sys as _sys
    import types as _types

    class _FakeMessage:
        content = [type("Block", (), {"text": "no tags here at all"})()]

    class _FakeMessages:
        def create(self, *a, **kw):
            return _FakeMessage()

    class _FakeClient:
        def __init__(self, *a, **kw):
            self.messages = _FakeMessages()

    fake_mod = _types.ModuleType("anthropic")
    fake_mod.Anthropic = _FakeClient
    monkeypatch.setitem(_sys.modules, "anthropic", fake_mod)

    result = rs.synthesize_rules_block(
        brain_dir=tmp_path,
        mandatory_lines=["[MANDATORY] anything"],
        cluster_lines=[],
        individual_lines=[],
    )
    assert result is None
    assert not (tmp_path / rs.CACHE_DIRNAME).exists()
