"""Tests for gradata.middleware.anthropic_adapter.

These tests mock the Anthropic SDK client — no real API calls are made.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Minimal stub for the `anthropic` package so the adapter imports cleanly
# in CI without the real SDK installed.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _stub_anthropic(monkeypatch):
    if "anthropic" not in sys.modules:
        stub = types.ModuleType("anthropic")
        stub.Anthropic = object  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "anthropic", stub)
    yield


# ---------------------------------------------------------------------------
# Fakes mimicking the parts of the Anthropic SDK the adapter touches.
# ---------------------------------------------------------------------------


class _FakeTextBlock:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.content = [_FakeTextBlock(text)]


class _FakeMessages:
    def __init__(self, reply: str = "hello world") -> None:
        self.reply = reply
        self.last_kwargs: dict = {}

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return _FakeResponse(self.reply)


class _FakeClient:
    def __init__(self, reply: str = "hello world") -> None:
        self.messages = _FakeMessages(reply)
        self.meta = "keep-me"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def brain_with_em_dash_rule(tmp_path: Path) -> Path:
    brain = tmp_path / "brain"
    brain.mkdir()
    (brain / "lessons.md").write_text(
        "[2026-04-13] [RULE:0.95] TONE: Never use em dashes in prose\n",
        encoding="utf-8",
    )
    return brain


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_wrap_anthropic_injects_rules_into_system(brain_with_em_dash_rule: Path):
    from gradata.middleware import wrap_anthropic

    client = _FakeClient()
    wrapped = wrap_anthropic(client, brain_path=brain_with_em_dash_rule)

    wrapped.messages.create(
        model="claude-sonnet-4-5",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=16,
    )

    system = client.messages.last_kwargs.get("system", "")
    assert "<brain-rules>" in system
    assert "TONE" in system
    assert "em dashes" in system


def test_wrap_anthropic_preserves_existing_system_prompt(brain_with_em_dash_rule: Path):
    from gradata.middleware import wrap_anthropic

    client = _FakeClient()
    wrapped = wrap_anthropic(client, brain_path=brain_with_em_dash_rule)

    wrapped.messages.create(
        model="claude-sonnet-4-5",
        system="You are a helpful assistant.",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=16,
    )

    system = client.messages.last_kwargs["system"]
    assert system.startswith("You are a helpful assistant.")
    assert "<brain-rules>" in system


def test_wrap_anthropic_strict_raises_on_violation(brain_with_em_dash_rule: Path):
    from gradata.middleware import RuleViolation, wrap_anthropic

    client = _FakeClient(reply="this response has an em dash \u2014 right here")
    wrapped = wrap_anthropic(client, brain_path=brain_with_em_dash_rule, strict=True)

    with pytest.raises(RuleViolation):
        wrapped.messages.create(
            model="claude-sonnet-4-5",
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=16,
        )


def test_wrap_anthropic_non_strict_logs_but_does_not_raise(
    brain_with_em_dash_rule: Path, caplog
):
    from gradata.middleware import wrap_anthropic

    client = _FakeClient(reply="em dash here \u2014 nope")
    wrapped = wrap_anthropic(client, brain_path=brain_with_em_dash_rule, strict=False)

    with caplog.at_level("WARNING", logger="gradata.middleware._core"):
        resp = wrapped.messages.create(
            model="claude-sonnet-4-5",
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=16,
        )
    assert resp is not None  # did not raise
    assert any("rule violation" in rec.message.lower() for rec in caplog.records)


def test_wrap_anthropic_bypass_env_disables_injection(
    brain_with_em_dash_rule: Path, monkeypatch
):
    from gradata.middleware import wrap_anthropic

    monkeypatch.setenv("GRADATA_BYPASS", "1")
    client = _FakeClient()
    wrapped = wrap_anthropic(client, brain_path=brain_with_em_dash_rule)

    wrapped.messages.create(
        model="claude-sonnet-4-5",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=16,
    )
    assert "system" not in client.messages.last_kwargs


def test_wrap_anthropic_no_brain_is_noop(tmp_path: Path):
    from gradata.middleware import wrap_anthropic

    client = _FakeClient()
    wrapped = wrap_anthropic(client, brain_path=tmp_path / "missing")

    wrapped.messages.create(
        model="claude-sonnet-4-5",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=16,
    )
    # No brain -> no system injected
    assert "system" not in client.messages.last_kwargs


def test_wrap_anthropic_delegates_other_attrs(brain_with_em_dash_rule: Path):
    from gradata.middleware import wrap_anthropic

    client = _FakeClient()
    wrapped = wrap_anthropic(client, brain_path=brain_with_em_dash_rule)
    assert wrapped.meta == "keep-me"


def test_anthropic_import_error_has_install_hint(monkeypatch):
    import importlib

    # Remove both anthropic stub and cached adapter so the import check runs.
    monkeypatch.delitem(sys.modules, "anthropic", raising=False)
    monkeypatch.delitem(
        sys.modules, "gradata.middleware.anthropic_adapter", raising=False,
    )

    # Force ImportError on `import anthropic` by installing a finder that
    # rejects it.
    import builtins

    real_import = builtins.__import__

    def _no_anthropic(name, *args, **kwargs):
        if name == "anthropic":
            raise ImportError("no anthropic")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _no_anthropic)

    mod = importlib.import_module("gradata.middleware.anthropic_adapter")
    with pytest.raises(ImportError) as exc:
        mod.AnthropicMiddleware(object())
    assert "pip install anthropic" in str(exc.value)
