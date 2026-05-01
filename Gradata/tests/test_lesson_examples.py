"""Tests for issue #129: Lesson.examples + Lesson.output_shape.

Covers:
    a. Lesson dataclass round-trip (format_lessons -> parse_lessons).
    b. Backward-compat: legacy markdown without Examples/Output shape.
    c. Rule engine formatting: structured <rule>/<good>/<bad>/<shape>
       XML when populated, legacy bullet otherwise.
    d. capture_example_from_correction appends de-duped Example, capped at 3.
"""

from __future__ import annotations

from gradata._types import Example, Lesson, LessonState
from gradata.enhancements.self_improvement import format_lessons, parse_lessons
from gradata.rules.rule_engine import (
    AppliedRule,
    capture_example_from_correction,
    format_rules_for_prompt,
)


def _make_lesson(**kwargs) -> Lesson:
    base = dict(
        date="2025-01-01",
        state=LessonState.RULE,
        confidence=0.92,
        category="DRAFTING",
        description="Use markdown tables for tabular comparisons",
    )
    base.update(kwargs)
    return Lesson(**base)


def test_lesson_round_trip_preserves_examples_and_output_shape():
    """Round-trip: format_lessons() -> parse_lessons() preserves new fields."""
    lesson = _make_lesson(
        examples=[
            Example(good="Use a table with 3 columns", bad="Use a long paragraph"),
            Example(good="Header row uses bold", bad="Header row left plain"),
        ],
        output_shape="format:markdown-table",
    )

    rendered = format_lessons([lesson])
    parsed = parse_lessons(rendered)

    assert len(parsed) == 1
    p = parsed[0]
    assert p.output_shape == "format:markdown-table"
    assert len(p.examples) == 2
    assert p.examples[0].good == "Use a table with 3 columns"
    assert p.examples[0].bad == "Use a long paragraph"
    assert p.examples[1].good == "Header row uses bold"
    assert p.examples[1].bad == "Header row left plain"
    # Core fields preserved too
    assert p.category == "DRAFTING"
    assert p.state == LessonState.RULE
    assert p.confidence == 0.92


def test_legacy_lesson_markdown_parses_without_examples():
    """Backward-compat: lessons.md predating issue #129 must still parse."""
    legacy = (
        "[2024-12-15] [RULE:0.91] TONE: Be concise — avoid filler phrases\n"
        "  Root cause: filler dilutes the signal\n"
        "  Fire count: 4 | Sessions since fire: 1 | Misfires: 0\n"
    )

    parsed = parse_lessons(legacy)

    assert len(parsed) == 1
    p = parsed[0]
    assert p.examples == []
    assert p.output_shape is None
    assert p.category == "TONE"
    assert p.fire_count == 4


def test_format_rules_for_prompt_renders_structured_xml_when_populated():
    """When examples or output_shape is set, render <rule><goal/><shape/><good/><bad/></rule>;
    otherwise fall back to the legacy bullet form."""
    rich_lesson = _make_lesson(
        examples=[Example(good="3-column table", bad="long paragraph")],
        output_shape="format:markdown-table",
    )
    plain_lesson = _make_lesson(
        category="TONE",
        description="Be concise",
        examples=[],
        output_shape=None,
    )

    rich = AppliedRule(
        rule_id="DRAFTING:0001",
        lesson=rich_lesson,
        relevance=1.0,
        instruction="Use markdown tables for tabular comparisons",
    )
    plain = AppliedRule(
        rule_id="TONE:0002",
        lesson=plain_lesson,
        relevance=1.0,
        instruction="Be concise",
    )

    # Rich rule: structured XML.
    out_rich = format_rules_for_prompt([rich], merge=False, entropy_search=False)
    assert "<brain-rules>" in out_rich
    assert "<rule>" in out_rich and "</rule>" in out_rich
    assert "<goal>Use markdown tables for tabular comparisons</goal>" in out_rich
    assert "<shape>format:markdown-table</shape>" in out_rich
    assert "<good>3-column table</good>" in out_rich
    assert "<bad>long paragraph</bad>" in out_rich

    # Plain rule: legacy bullet, no <rule> wrapper.
    out_plain = format_rules_for_prompt([plain], merge=False, entropy_search=False)
    assert "<rule>" not in out_plain
    assert "- Be concise" in out_plain


def test_capture_example_appends_dedup_and_caps_at_three():
    """capture_example_from_correction appends Example(good, bad), de-dupes
    identical pairs, and caps the list at 3 entries."""
    lesson = _make_lesson()

    # First capture
    capture_example_from_correction(lesson, draft="bad v1", corrected="good v1")
    assert len(lesson.examples) == 1
    assert lesson.examples[0].good == "good v1"
    assert lesson.examples[0].bad == "bad v1"

    # Duplicate is skipped
    capture_example_from_correction(lesson, draft="bad v1", corrected="good v1")
    assert len(lesson.examples) == 1

    # Append two more distinct
    capture_example_from_correction(lesson, draft="bad v2", corrected="good v2")
    capture_example_from_correction(lesson, draft="bad v3", corrected="good v3")
    assert len(lesson.examples) == 3

    # Fourth distinct trims to most recent 3 (cap=3)
    capture_example_from_correction(lesson, draft="bad v4", corrected="good v4")
    assert len(lesson.examples) == 3
    assert [e.good for e in lesson.examples] == ["good v2", "good v3", "good v4"]
    assert [e.bad for e in lesson.examples] == ["bad v2", "bad v3", "bad v4"]
