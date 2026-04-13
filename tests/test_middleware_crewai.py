"""Tests for gradata.middleware.crewai_adapter (no real CrewAI calls)."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def brain_with_em_dash_rule(tmp_path: Path) -> Path:
    brain = tmp_path / "brain"
    brain.mkdir()
    (brain / "lessons.md").write_text(
        "[2026-04-13] [RULE:0.95] TONE: Never use em dashes in prose\n",
        encoding="utf-8",
    )
    return brain


def test_crewai_guard_passes_clean_output(brain_with_em_dash_rule: Path):
    from gradata.middleware import CrewAIGuard

    guard = CrewAIGuard(brain_path=brain_with_em_dash_rule)
    ok, result = guard("A perfectly clean string.")
    assert ok is True
    assert result == "A perfectly clean string."


def test_crewai_guard_blocks_violation_when_strict(brain_with_em_dash_rule: Path):
    from gradata.middleware import CrewAIGuard

    guard = CrewAIGuard(brain_path=brain_with_em_dash_rule, strict=True)
    ok, result = guard("has em dash \u2014 here")
    assert ok is False
    assert "em-dash" in result or "em dash" in result.lower()


def test_crewai_guard_non_strict_allows_violation(brain_with_em_dash_rule: Path):
    from gradata.middleware import CrewAIGuard

    guard = CrewAIGuard(brain_path=brain_with_em_dash_rule, strict=False)
    text = "has em dash \u2014 here"
    ok, result = guard(text)
    assert ok is True
    assert result == text


def test_crewai_guard_extracts_text_from_object(brain_with_em_dash_rule: Path):
    from gradata.middleware import CrewAIGuard

    class FakeOutput:
        def __init__(self, raw: str) -> None:
            self.raw = raw

    guard = CrewAIGuard(brain_path=brain_with_em_dash_rule, strict=True)
    ok, _ = guard(FakeOutput("bad \u2014 output"))
    assert ok is False


def test_crewai_guard_bypass_env(brain_with_em_dash_rule: Path, monkeypatch):
    from gradata.middleware import CrewAIGuard

    monkeypatch.setenv("GRADATA_BYPASS", "1")
    guard = CrewAIGuard(brain_path=brain_with_em_dash_rule, strict=True)
    ok, _ = guard("bad \u2014 output")
    assert ok is True  # bypass disables enforcement


def test_crewai_guard_empty_output_passes(brain_with_em_dash_rule: Path):
    from gradata.middleware import CrewAIGuard

    guard = CrewAIGuard(brain_path=brain_with_em_dash_rule, strict=True)
    ok, result = guard("")
    assert ok is True
    assert result == ""
