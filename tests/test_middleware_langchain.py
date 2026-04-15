"""Tests for gradata.middleware.langchain_adapter (no real LLM calls)."""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Stub out langchain_core so tests run in CI without the real package.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _stub_langchain(monkeypatch):
    if "langchain_core" not in sys.modules:
        lc = types.ModuleType("langchain_core")
        callbacks_mod = types.ModuleType("langchain_core.callbacks")
        messages_mod = types.ModuleType("langchain_core.messages")

        class _BaseCallbackHandler:
            def __init__(self) -> None:
                pass

        class _SystemMessage:
            def __init__(self, content: str) -> None:
                self.content = content
                self.type = "system"

        callbacks_mod.BaseCallbackHandler = _BaseCallbackHandler
        messages_mod.SystemMessage = _SystemMessage
        lc.callbacks = callbacks_mod
        lc.messages = messages_mod

        monkeypatch.setitem(sys.modules, "langchain_core", lc)
        monkeypatch.setitem(sys.modules, "langchain_core.callbacks", callbacks_mod)
        monkeypatch.setitem(sys.modules, "langchain_core.messages", messages_mod)

        # Force a fresh import of the adapter so it picks up the stub.
        monkeypatch.delitem(
            sys.modules, "gradata.middleware.langchain_adapter", raising=False,
        )
    yield


@pytest.fixture
def brain_with_em_dash_rule(tmp_path: Path) -> Path:
    brain = tmp_path / "brain"
    brain.mkdir()
    (brain / "lessons.md").write_text(
        "[2026-04-13] [RULE:0.95] TONE: Never use em dashes in prose\n",
        encoding="utf-8",
    )
    return brain


# Simple fakes for LangChain message + generation types
class _FakeMessage:
    def __init__(self, content: str, type_: str = "human") -> None:
        self.content = content
        self.type = type_


class _FakeGeneration:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeLLMResult:
    def __init__(self, text: str) -> None:
        self.generations = [[_FakeGeneration(text)]]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_on_llm_start_prepends_block_to_first_prompt(brain_with_em_dash_rule: Path):
    from gradata.middleware.langchain_adapter import LangChainCallback

    cb = LangChainCallback(brain_path=brain_with_em_dash_rule)
    prompts = ["User: hi"]
    cb.on_llm_start({}, prompts)
    assert prompts[0].startswith("<brain-rules>")
    assert "User: hi" in prompts[0]


def test_on_chat_model_start_inserts_system_message(brain_with_em_dash_rule: Path):
    from gradata.middleware.langchain_adapter import LangChainCallback

    cb = LangChainCallback(brain_path=brain_with_em_dash_rule)
    batches = [[_FakeMessage("hi", "human")]]
    cb.on_chat_model_start({}, batches)
    first = batches[0][0]
    assert first.type == "system"
    assert "<brain-rules>" in first.content


def test_on_llm_start_prepends_block_to_every_prompt_in_batch(
    brain_with_em_dash_rule: Path,
):
    from gradata.middleware.langchain_adapter import LangChainCallback

    cb = LangChainCallback(brain_path=brain_with_em_dash_rule)
    prompts = ["User: first", "User: second", "User: third"]
    cb.on_llm_start({}, prompts)
    for p in prompts:
        assert p.startswith("<brain-rules>")


def test_on_chat_model_start_preserves_multimodal_list_system(
    brain_with_em_dash_rule: Path,
):
    from gradata.middleware.langchain_adapter import LangChainCallback

    cb = LangChainCallback(brain_path=brain_with_em_dash_rule)
    original_blocks = [{"type": "text", "text": "You are kind."}]
    sys_msg = _FakeMessage.__new__(_FakeMessage)
    sys_msg.content = original_blocks
    sys_msg.type = "system"
    batches = [[sys_msg, _FakeMessage("hi", "human")]]
    cb.on_chat_model_start({}, batches)
    # List structure preserved; new block appended, not stringified.
    assert isinstance(sys_msg.content, list)
    assert sys_msg.content[0] == {"type": "text", "text": "You are kind."}
    assert any(
        isinstance(b, dict) and "<brain-rules>" in str(b.get("text", ""))
        for b in sys_msg.content
    )


def test_on_chat_model_start_extends_existing_system(brain_with_em_dash_rule: Path):
    from gradata.middleware.langchain_adapter import LangChainCallback

    cb = LangChainCallback(brain_path=brain_with_em_dash_rule)
    batches = [[_FakeMessage("You are kind.", "system"), _FakeMessage("hi", "human")]]
    cb.on_chat_model_start({}, batches)
    assert batches[0][0].type == "system"
    assert batches[0][0].content.startswith("You are kind.")
    assert "<brain-rules>" in batches[0][0].content


@pytest.mark.parametrize("strict", [True, False])
def test_on_llm_end_strictness(brain_with_em_dash_rule: Path, strict: bool):
    from gradata.middleware import RuleViolation
    from gradata.middleware.langchain_adapter import LangChainCallback

    cb = LangChainCallback(brain_path=brain_with_em_dash_rule, strict=strict)
    result = _FakeLLMResult("bad \u2014 output")
    if strict:
        with pytest.raises(RuleViolation):
            cb.on_llm_end(result)
    else:
        cb.on_llm_end(result)  # must not raise


def test_bypass_env_skips_injection(brain_with_em_dash_rule: Path, monkeypatch):
    from gradata.middleware.langchain_adapter import LangChainCallback

    monkeypatch.setenv("GRADATA_BYPASS", "1")
    cb = LangChainCallback(brain_path=brain_with_em_dash_rule)
    prompts = ["User: hi"]
    cb.on_llm_start({}, prompts)
    assert prompts[0] == "User: hi"  # unchanged


def test_langchain_import_error_has_install_hint(monkeypatch):
    # Drop the stub + cached adapter; force-fail the import.
    monkeypatch.delitem(sys.modules, "langchain_core", raising=False)
    monkeypatch.delitem(sys.modules, "langchain_core.callbacks", raising=False)
    monkeypatch.delitem(sys.modules, "langchain_core.messages", raising=False)
    monkeypatch.delitem(
        sys.modules, "gradata.middleware.langchain_adapter", raising=False,
    )

    import builtins

    real_import = builtins.__import__

    def _no_langchain(name, *args, **kwargs):
        if name.startswith("langchain_core"):
            raise ImportError("no langchain_core")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _no_langchain)
    mod = importlib.import_module("gradata.middleware.langchain_adapter")
    with pytest.raises(ImportError) as exc:
        mod.LangChainCallback()
    assert "langchain-core" in str(exc.value)
