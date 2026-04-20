"""Tests for Correction Scope Tagging (Task 2: SDK P0 hardening).

Verifies:
- CorrectionScope enum exists with 4 values
- Default correction gets domain scope
- Explicit scope override works
- Scope flows into lesson's scope_json
- ONE_OFF lessons never graduate past INSTINCT
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gradata._types import CorrectionScope, Lesson, LessonState


# ---------------------------------------------------------------------------
# CorrectionScope enum
# ---------------------------------------------------------------------------

def test_correction_scope_enum_has_four_values():
    """CorrectionScope has exactly UNIVERSAL, DOMAIN, PROJECT, ONE_OFF."""
    assert CorrectionScope.UNIVERSAL.value == "universal"
    assert CorrectionScope.DOMAIN.value == "domain"
    assert CorrectionScope.PROJECT.value == "project"
    assert CorrectionScope.ONE_OFF.value == "one_off"
    assert len(CorrectionScope) == 4


# ---------------------------------------------------------------------------
# Default scope = domain
# ---------------------------------------------------------------------------

def test_default_scope_is_domain(tmp_path: Path):
    """brain.correct() without scope param defaults to 'domain'."""
    from tests.conftest import init_brain

    brain = init_brain(tmp_path)
    result = brain.correct("Use em dash — here", "Use colon: here")
    # The correction data should have correction_scope = "domain"
    assert result.get("correction_scope") == "domain"


# ---------------------------------------------------------------------------
# Explicit scope override
# ---------------------------------------------------------------------------

def test_explicit_scope_universal(tmp_path: Path):
    """brain.correct(scope='universal') sets correction_scope to universal."""
    from tests.conftest import init_brain

    brain = init_brain(tmp_path)
    result = brain.correct("bad output", "good output", scope="universal")
    assert result.get("correction_scope") == "universal"


def test_explicit_scope_one_off(tmp_path: Path):
    """brain.correct(scope='one_off') sets correction_scope to one_off."""
    from tests.conftest import init_brain

    brain = init_brain(tmp_path)
    result = brain.correct("wrong thing", "right thing", scope="one_off")
    assert result.get("correction_scope") == "one_off"


# ---------------------------------------------------------------------------
# Scope flows into lesson scope_json
# ---------------------------------------------------------------------------

def test_scope_in_lesson_scope_json(tmp_path: Path):
    """correction_scope appears in the new lesson's scope_json."""
    from tests.conftest import init_brain
    from gradata.enhancements.self_improvement import parse_lessons

    brain = init_brain(tmp_path)
    # Use a major edit to ensure severity threshold is met and lesson is created
    brain.correct(
        "This is a completely wrong paragraph that needs total rewriting with different content.",
        "Here is the corrected version with entirely new accurate information and proper formatting.",
        scope="project",
    )

    lessons_path = brain._find_lessons_path()
    assert lessons_path and lessons_path.is_file(), "lessons.md not created"
    text = lessons_path.read_text(encoding="utf-8")
    lessons = parse_lessons(text)
    assert len(lessons) >= 1, f"No lessons created. File content:\n{text[:500]}"
    # Find the newly created lesson with correction_scope
    new_lessons = [l for l in lessons if l.scope_json and "correction_scope" in l.scope_json]
    assert len(new_lessons) >= 1, f"No lesson with correction_scope found. scope_jsons: {[l.scope_json for l in lessons]}"
    scope_data = json.loads(new_lessons[0].scope_json)
    assert scope_data.get("correction_scope") == "project"


# ---------------------------------------------------------------------------
# ONE_OFF never graduates past INSTINCT
# ---------------------------------------------------------------------------

def test_one_off_never_graduates_past_instinct():
    """A one_off lesson with high confidence stays at INSTINCT."""
    from gradata.enhancements.self_improvement import graduate

    scope = json.dumps({"correction_scope": "one_off"})
    lesson = Lesson(
        date="2026-04-07",
        state=LessonState.INSTINCT,
        confidence=0.95,  # Way above PATTERN threshold
        category="DRAFTING",
        description="Fix this one specific typo",
        fire_count=10,  # Meets all fire count thresholds
        scope_json=scope,
    )

    active, graduated = graduate([lesson])
    # Should still be INSTINCT — blocked from promotion
    assert lesson.state == LessonState.INSTINCT
    assert lesson in active


def test_one_off_at_pattern_does_not_promote_to_rule():
    """Even if a one_off lesson somehow reaches PATTERN, it shouldn't promote to RULE."""
    from gradata.enhancements.self_improvement import graduate

    scope = json.dumps({"correction_scope": "one_off"})
    lesson = Lesson(
        date="2026-04-07",
        state=LessonState.PATTERN,
        confidence=0.95,
        category="DRAFTING",
        description="Fix this one specific formatting issue",
        fire_count=10,
        scope_json=scope,
    )

    active, graduated = graduate([lesson])
    # Should stay at PATTERN — blocked from RULE promotion
    assert lesson.state == LessonState.PATTERN
    assert lesson in active


def test_non_one_off_can_graduate():
    """A domain-scoped lesson with high confidence DOES graduate normally."""
    from gradata.enhancements.self_improvement import graduate

    scope = json.dumps({"correction_scope": "domain"})
    lesson = Lesson(
        date="2026-04-07",
        state=LessonState.INSTINCT,
        confidence=0.65,  # Above PATTERN threshold
        category="DRAFTING",
        description="Never use em dashes in prose",
        fire_count=5,
        scope_json=scope,
    )

    active, graduated = graduate([lesson])
    # Should promote to PATTERN
    assert lesson.state == LessonState.PATTERN


# ---------------------------------------------------------------------------
# Free-form applies_to scope binding (sim21 ask)
# ---------------------------------------------------------------------------

def test_applies_to_persisted_on_event(tmp_path: Path):
    """brain.correct(applies_to='client:acme') persists the token on the event."""
    from tests.conftest import init_brain

    brain = init_brain(tmp_path)
    result = brain.correct(
        "Dear Sir/Madam,",
        "Hey Acme team,",
        applies_to="client:acme",
    )
    assert result.get("applies_to") == "client:acme"
    assert result["data"]["applies_to"] == "client:acme"
    assert result["data"]["scope"]["applies_to"] == "client:acme"
    assert "applies_to:client:acme" in result["tags"]


def test_applies_to_none_is_backward_compatible(tmp_path: Path):
    """Omitting applies_to leaves the event clear of the token (legacy behaviour)."""
    from tests.conftest import init_brain

    brain = init_brain(tmp_path)
    result = brain.correct("bad output", "good output")
    assert "applies_to" not in result
    assert "applies_to" not in result.get("data", {})
    assert not any(t.startswith("applies_to:") for t in result.get("tags", []))


def test_applies_to_empty_string_collapses_to_none(tmp_path: Path):
    """Empty / whitespace-only applies_to is normalised away."""
    from tests.conftest import init_brain

    brain = init_brain(tmp_path)
    result = brain.correct("bad output", "good output", applies_to="   ")
    assert "applies_to" not in result
    assert "applies_to" not in result.get("data", {})


def test_applies_to_propagates_to_lesson_scope_json(tmp_path: Path):
    """applies_to appears in the new lesson's scope_json alongside correction_scope."""
    from gradata.enhancements.self_improvement import parse_lessons
    from tests.conftest import init_brain

    brain = init_brain(tmp_path)
    brain.correct(
        "This is a completely wrong paragraph that needs total rewriting with different content.",
        "Here is the corrected version with entirely new accurate information and proper formatting.",
        applies_to="task:emails",
    )

    lessons_path = brain._find_lessons_path()
    assert lessons_path and lessons_path.is_file(), "lessons.md not created"
    text = lessons_path.read_text(encoding="utf-8")
    lessons = parse_lessons(text)
    tagged = [
        l for l in lessons
        if l.scope_json and "applies_to" in l.scope_json
    ]
    assert tagged, f"No lesson carried applies_to. scope_jsons={[l.scope_json for l in lessons]}"
    scope_data = json.loads(tagged[0].scope_json)
    assert scope_data.get("applies_to") == "task:emails"
    assert scope_data.get("correction_scope") == "domain"  # default preserved
