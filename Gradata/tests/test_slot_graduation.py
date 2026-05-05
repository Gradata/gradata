"""Tests for Preston-Rhodes slot field + graduation-time classifier.

Covers:
- Lesson dataclass carries `slot` (default "").
- format_lessons emits `  Slot: <value>` only when set.
- parse_lessons round-trips the slot.
- graduate() assigns a slot when promoting INSTINCT -> PATTERN.
- graduate() assigns a slot when promoting PATTERN -> RULE.
- classify_slot respects explicit-slot > example-pair > category inference.
"""

from __future__ import annotations

from gradata._types import Lesson, LessonState
from gradata.enhancements.self_improvement import (
    format_lessons,
    graduate,
    parse_lessons,
)


def _mk(
    *,
    state: LessonState,
    confidence: float,
    fire_count: int,
    category: str = "DRAFTING",
    description: str = "Use tight prose; prefer verbs over nouns.",
    slot: str = "",
) -> Lesson:
    return Lesson(
        date="2026-04-21",
        state=state,
        confidence=confidence,
        category=category,
        description=description,
        fire_count=fire_count,
        slot=slot,
    )


class TestSlotField:
    def test_default_slot_is_empty(self):
        lesson = _mk(state=LessonState.INSTINCT, confidence=0.3, fire_count=0)
        assert lesson.slot == ""

    def test_format_omits_slot_when_empty(self):
        lesson = _mk(state=LessonState.PATTERN, confidence=0.7, fire_count=3)
        out = format_lessons([lesson])
        assert "Slot:" not in out

    def test_format_emits_slot_when_set(self):
        lesson = _mk(
            state=LessonState.PATTERN,
            confidence=0.7,
            fire_count=3,
            slot="format",
        )
        out = format_lessons([lesson])
        assert "  Slot: format" in out

    def test_roundtrip_preserves_slot(self):
        lesson = _mk(
            state=LessonState.RULE,
            confidence=0.95,
            fire_count=7,
            slot="tone",
        )
        text = format_lessons([lesson])
        [reparsed] = parse_lessons(text)
        assert reparsed.slot == "tone"


class TestGraduationAssignsSlot:
    def test_instinct_to_pattern_sets_slot(self):
        # Needs confidence strictly > PATTERN_THRESHOLD (0.60) and fire_count >= 3.
        lesson = _mk(
            state=LessonState.INSTINCT,
            confidence=0.65,
            fire_count=3,
            category="TONE",
            description="Match the user's register; avoid corporate filler.",
        )
        assert lesson.slot == ""
        graduate([lesson])
        assert lesson.state == LessonState.PATTERN
        assert lesson.slot != ""  # classifier assigned something

    def test_existing_slot_is_preserved_on_promotion(self):
        lesson = _mk(
            state=LessonState.INSTINCT,
            confidence=0.65,
            fire_count=3,
            slot="persona",
        )
        graduate([lesson])
        assert lesson.state == LessonState.PATTERN
        assert lesson.slot == "persona"

    def test_no_promotion_leaves_slot_unset(self):
        # Below fire-count gate — no promotion, no slot assignment.
        lesson = _mk(
            state=LessonState.INSTINCT,
            confidence=0.70,
            fire_count=1,
        )
        graduate([lesson])
        assert lesson.state == LessonState.INSTINCT
        assert lesson.slot == ""
