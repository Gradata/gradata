"""Tests for gradata.middleware.openai_adapter (mocked; no real API calls)."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _stub_openai(monkeypatch):
    if "openai" not in sys.modules:
        stub = types.ModuleType("openai")
        stub.OpenAI = object  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "openai", stub)
    yield


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, reply: str = "ok") -> None:
        self.reply = reply
        self.last_kwargs: dict = {}

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return _FakeResponse(self.reply)


class _FakeChat:
    def __init__(self, reply: str = "ok") -> None:
        self.completions = _FakeCompletions(reply)


class _FakeClient:
    def __init__(self, reply: str = "ok") -> None:
        self.chat = _FakeChat(reply)
        self.meta = "delegate"


@pytest.fixture
def brain_with_em_dash_rule(tmp_path: Path) -> Path:
    brain = tmp_path / "brain"
    brain.mkdir()
    (brain / "lessons.md").write_text(
        "[2026-04-13] [RULE:0.95] TONE: Never use em dashes in prose\n",
        encoding="utf-8",
    )
    return brain


def test_wrap_openai_prepends_system_message(brain_with_em_dash_rule: Path):
    from gradata.middleware import wrap_openai

    client = _FakeClient()
    wrapped = wrap_openai(client, brain_path=brain_with_em_dash_rule)

    wrapped.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "hi"}],
    )
    sent = client.chat.completions.last_kwargs["messages"]
    assert sent[0]["role"] == "system"
    assert "<brain-rules>" in sent[0]["content"]
    assert sent[1]["role"] == "user"


def test_wrap_openai_extends_existing_system(brain_with_em_dash_rule: Path):
    from gradata.middleware import wrap_openai

    client = _FakeClient()
    wrapped = wrap_openai(client, brain_path=brain_with_em_dash_rule)
    wrapped.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Be terse."},
            {"role": "user", "content": "hi"},
        ],
    )
    sent = client.chat.completions.last_kwargs["messages"]
    assert sent[0]["role"] == "system"
    assert sent[0]["content"].startswith("Be terse.")
    assert "<brain-rules>" in sent[0]["content"]


def test_wrap_openai_strict_raises_on_violation(brain_with_em_dash_rule: Path):
    from gradata.middleware import RuleViolation, wrap_openai

    client = _FakeClient(reply="bad \u2014 output")
    wrapped = wrap_openai(client, brain_path=brain_with_em_dash_rule, strict=True)
    with pytest.raises(RuleViolation):
        wrapped.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "hi"}],
        )


def test_wrap_openai_non_strict_does_not_raise(brain_with_em_dash_rule: Path):
    from gradata.middleware import wrap_openai

    client = _FakeClient(reply="bad \u2014 output")
    wrapped = wrap_openai(client, brain_path=brain_with_em_dash_rule, strict=False)
    # Must not raise
    resp = wrapped.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "hi"}],
    )
    assert resp is not None


def test_wrap_openai_bypass_env(brain_with_em_dash_rule: Path, monkeypatch):
    from gradata.middleware import wrap_openai

    monkeypatch.setenv("GRADATA_BYPASS", "1")
    client = _FakeClient()
    wrapped = wrap_openai(client, brain_path=brain_with_em_dash_rule)
    wrapped.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "hi"}],
    )
    sent = client.chat.completions.last_kwargs["messages"]
    # Unchanged — no system message prepended
    assert sent[0]["role"] == "user"


def test_wrap_openai_delegates_other_attrs(brain_with_em_dash_rule: Path):
    from gradata.middleware import wrap_openai

    client = _FakeClient()
    wrapped = wrap_openai(client, brain_path=brain_with_em_dash_rule)
    assert wrapped.meta == "delegate"


def test_openai_import_error_has_install_hint(monkeypatch):
    import builtins
    import importlib

    monkeypatch.delitem(sys.modules, "openai", raising=False)
    monkeypatch.delitem(sys.modules, "gradata.middleware.openai_adapter", raising=False)

    real_import = builtins.__import__

    def _no_openai(name, *args, **kwargs):
        if name == "openai":
            raise ImportError("no openai")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _no_openai)
    mod = importlib.import_module("gradata.middleware.openai_adapter")
    with pytest.raises(ImportError) as exc:
        mod.OpenAIMiddleware(object())
    assert "pip install openai" in str(exc.value)
