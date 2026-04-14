"""Tests for the middleware core (rule source, injection, enforcement)."""

from __future__ import annotations

from pathlib import Path

import pytest

from gradata.middleware import (
    RuleSource,
    RuleViolation,
    build_brain_rules_block,
    check_output,
    is_bypassed,
)


def test_rule_source_from_static_lessons_selects_rule_and_pattern():
    src = RuleSource(
        lessons=[
            {"state": "RULE", "confidence": 0.95, "category": "TONE",
             "description": "Never use em dashes"},
            {"state": "PATTERN", "confidence": 0.70, "category": "STRUCTURE",
             "description": "Lead with the answer"},
            {"state": "INSTINCT", "confidence": 0.55, "category": "DRAFTING",
             "description": "Avoid padding"},
        ],
    )
    selected = src.select()
    assert len(selected) == 2
    # RULE comes first (priority bucket), then PATTERN.
    assert selected[0].state == "RULE"
    assert selected[1].state == "PATTERN"


def test_build_brain_rules_block_wraps_in_xml():
    src = RuleSource(
        lessons=[
            {"state": "RULE", "confidence": 0.95, "category": "TONE",
             "description": "Never use em dashes"},
        ],
    )
    block = build_brain_rules_block(src)
    assert block.startswith("<brain-rules>")
    assert block.endswith("</brain-rules>")
    assert "[RULE:0.95]" in block
    assert "TONE" in block


def test_build_brain_rules_block_respects_max_rules():
    lessons = [
        {"state": "RULE", "confidence": min(1.0, 0.90 + i / 200), "category": f"C{i}",
         "description": f"desc {i}"}
        for i in range(20)
    ]
    src = RuleSource(lessons=lessons, max_rules=5)
    block = build_brain_rules_block(src)
    assert block.count("[RULE:") == 5


def test_check_output_finds_em_dash_violation():
    src = RuleSource(
        lessons=[
            {"state": "RULE", "confidence": 0.95, "category": "TONE",
             "description": "Never use em dashes"},
        ],
    )
    violations = check_output(src, "no good \u2014 here", strict=False)
    assert len(violations) == 1
    assert violations[0].pattern_name == "em-dash"


def test_check_output_strict_raises():
    src = RuleSource(
        lessons=[
            {"state": "RULE", "confidence": 0.95, "category": "TONE",
             "description": "Never use em dashes"},
        ],
    )
    with pytest.raises(RuleViolation):
        check_output(src, "bad \u2014 text", strict=True)


def test_check_output_ignores_non_rule_tier():
    src = RuleSource(
        lessons=[
            {"state": "PATTERN", "confidence": 0.80, "category": "TONE",
             "description": "Never use em dashes"},
        ],
    )
    # PATTERN-tier is injected but not enforced
    assert check_output(src, "bad \u2014 text", strict=False) == []


def test_is_bypassed_env(monkeypatch):
    monkeypatch.setenv("GRADATA_BYPASS", "1")
    assert is_bypassed() is True
    monkeypatch.setenv("GRADATA_BYPASS", "0")
    assert is_bypassed() is False
    monkeypatch.delenv("GRADATA_BYPASS", raising=False)
    assert is_bypassed() is False


def test_bypass_disables_block_and_check(monkeypatch):
    monkeypatch.setenv("GRADATA_BYPASS", "1")
    src = RuleSource(
        lessons=[
            {"state": "RULE", "confidence": 0.95, "category": "TONE",
             "description": "Never use em dashes"},
        ],
    )
    assert build_brain_rules_block(src) == ""
    assert check_output(src, "bad \u2014 text", strict=True) == []


def test_rule_source_from_brain_path(tmp_path: Path):
    brain = tmp_path / "brain"
    brain.mkdir()
    (brain / "lessons.md").write_text(
        "[2026-04-13] [RULE:0.95] TONE: Never use em dashes in prose\n"
        "[2026-04-13] [PATTERN:0.70] STRUCTURE: Lead with the answer\n",
        encoding="utf-8",
    )
    src = RuleSource(brain_path=brain)
    selected = src.select()
    assert len(selected) == 2
    cats = {l.category for l in selected}
    assert "TONE" in cats
    assert "STRUCTURE" in cats


def test_rule_source_missing_brain_returns_empty(tmp_path: Path):
    src = RuleSource(brain_path=tmp_path / "does-not-exist")
    assert src.select() == []
    assert build_brain_rules_block(src) == ""


def test_rule_source_skips_non_numeric_confidence():
    # Malformed caller-supplied lessons must not abort the injection path.
    src = RuleSource(
        lessons=[
            {"state": "RULE", "confidence": "high", "category": "TONE",
             "description": "malformed"},
            {"state": "RULE", "confidence": 0.95, "category": "TONE",
             "description": "Never use em dashes"},
        ],
    )
    selected = src.select()
    assert len(selected) == 1
    assert selected[0].description == "Never use em dashes"
