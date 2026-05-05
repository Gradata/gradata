"""Tests for brain.share() and brain.absorb() — team rule sharing."""

from __future__ import annotations

from tests.conftest import init_brain


def test_share_returns_package_structure(tmp_path):
    brain = init_brain(tmp_path)
    package = brain.share()
    assert "brain_id" in package
    assert "exported_at" in package
    assert "rules" in package
    assert "rule_count" in package
    assert isinstance(package["rules"], list)


def test_share_only_exports_graduated_rules(tmp_path):
    brain = init_brain(tmp_path)
    # Create a correction (will be INSTINCT, not graduated)
    brain.correct("working good", "working well", category="DRAFTING", session=1)
    package = brain.share()
    # INSTINCT lessons should NOT be exported
    assert package["rule_count"] == 0


def test_share_exports_pattern_and_rule(tmp_path):
    """Manually write PATTERN/RULE lessons and verify they export."""
    brain = init_brain(tmp_path)

    from gradata._types import CorrectionType, Lesson, LessonState
    from gradata.enhancements.self_improvement import format_lessons

    lessons = [
        Lesson(
            date="2026-04-06",
            state=LessonState.RULE,
            confidence=0.95,
            category="DRAFTING",
            description="Use active voice in all communications",
            correction_type=CorrectionType.BEHAVIORAL,
            fire_count=12,
        ),
        Lesson(
            date="2026-04-06",
            state=LessonState.PATTERN,
            confidence=0.70,
            category="TONE",
            description="Be concise and direct",
            correction_type=CorrectionType.PREFERENCE,
            fire_count=5,
        ),
        Lesson(
            date="2026-04-06",
            state=LessonState.INSTINCT,
            confidence=0.40,
            category="FORMAT",
            description="Use bullet points for lists",
            correction_type=CorrectionType.BEHAVIORAL,
            fire_count=1,
        ),
    ]

    lessons_path = brain._find_lessons_path(create=True)
    assert lessons_path is not None
    lessons_path.write_text(format_lessons(lessons), encoding="utf-8")

    package = brain.share()
    assert package["rule_count"] == 2  # RULE + PATTERN only
    categories = {r["category"] for r in package["rules"]}
    assert "DRAFTING" in categories
    assert "TONE" in categories
    assert "FORMAT" not in categories  # INSTINCT excluded


def test_absorb_imports_rules(tmp_path):
    brain = init_brain(tmp_path)

    package = {
        "brain_id": "test-source",
        "exported_at": "2026-04-06T00:00:00Z",
        "rules": [
            {
                "category": "DRAFTING",
                "description": "Use active voice",
                "confidence": 0.95,
                "state": "RULE",
                "fire_count": 12,
                "correction_type": "behavioral",
            },
        ],
        "rule_count": 1,
        "proof": {},
    }
    result = brain.absorb(package)
    assert result["absorbed"] == 1
    assert result["skipped"] == 0


def test_absorb_skips_duplicates(tmp_path):
    brain = init_brain(tmp_path)
    package = {
        "brain_id": "test",
        "rules": [
            {
                "category": "DRAFTING",
                "description": "Use active voice",
                "confidence": 0.95,
                "state": "RULE",
                "fire_count": 12,
                "correction_type": "behavioral",
            },
        ],
        "rule_count": 1,
    }
    # First absorb
    result1 = brain.absorb(package)
    assert result1["absorbed"] == 1
    # Second absorb — should skip duplicate
    result2 = brain.absorb(package)
    assert result2["skipped"] == 1
    assert result2["absorbed"] == 0


def test_absorb_imports_as_instinct(tmp_path):
    brain = init_brain(tmp_path)
    package = {
        "brain_id": "test",
        "rules": [
            {
                "category": "TONE",
                "description": "Be concise",
                "confidence": 0.95,
                "state": "RULE",
                "fire_count": 20,
                "correction_type": "behavioral",
            },
        ],
        "rule_count": 1,
    }
    brain.absorb(package)
    # Verify the imported rule is INSTINCT, not RULE
    from gradata.enhancements.self_improvement import parse_lessons

    lessons_path = brain._find_lessons_path()
    assert lessons_path is not None
    lessons = parse_lessons(lessons_path.read_text(encoding="utf-8"))
    tone_lessons = [l for l in lessons if l.category == "TONE"]
    assert len(tone_lessons) == 1
    assert tone_lessons[0].state.value == "INSTINCT"
    assert tone_lessons[0].confidence == 0.40


def test_absorb_sets_agent_type_shared(tmp_path):
    brain = init_brain(tmp_path)
    package = {
        "brain_id": "test",
        "rules": [
            {
                "category": "PROCESS",
                "description": "Always verify before submitting",
                "confidence": 0.90,
                "state": "RULE",
                "fire_count": 8,
                "correction_type": "procedural",
            },
        ],
        "rule_count": 1,
    }
    brain.absorb(package)

    from gradata.enhancements.self_improvement import parse_lessons

    lessons_path = brain._find_lessons_path()
    assert lessons_path is not None
    lessons = parse_lessons(lessons_path.read_text(encoding="utf-8"))
    process_lessons = [l for l in lessons if l.category == "PROCESS"]
    assert len(process_lessons) == 1
    assert process_lessons[0].agent_type == "shared"


def test_share_then_absorb_round_trip(tmp_path):
    """Full round trip: brain A shares, brain B absorbs."""
    brain_a = init_brain(tmp_path / "a")
    brain_b = init_brain(tmp_path / "b")

    # Brain A's share will be empty (no graduated rules from just corrections)
    package = brain_a.share()
    result = brain_b.absorb(package)
    assert result["absorbed"] == 0  # Nothing graduated yet


def test_absorb_multiple_rules(tmp_path):
    brain = init_brain(tmp_path)
    package = {
        "brain_id": "test",
        "rules": [
            {
                "category": "DRAFTING",
                "description": "Use active voice",
                "confidence": 0.95,
                "state": "RULE",
                "fire_count": 12,
                "correction_type": "behavioral",
            },
            {
                "category": "TONE",
                "description": "Be concise and direct",
                "confidence": 0.75,
                "state": "PATTERN",
                "fire_count": 6,
                "correction_type": "preference",
            },
            {
                "category": "PROCESS",
                "description": "Always verify data before sending",
                "confidence": 0.90,
                "state": "RULE",
                "fire_count": 10,
                "correction_type": "procedural",
            },
        ],
        "rule_count": 3,
    }
    result = brain.absorb(package)
    assert result["absorbed"] == 3
    assert result["skipped"] == 0
    assert result["total_rules_in_package"] == 3


def test_absorb_empty_package(tmp_path):
    brain = init_brain(tmp_path)
    package = {
        "brain_id": "empty",
        "rules": [],
        "rule_count": 0,
    }
    result = brain.absorb(package)
    assert result["absorbed"] == 0
    assert result["skipped"] == 0


def test_absorb_invalid_correction_type_defaults(tmp_path):
    brain = init_brain(tmp_path)
    package = {
        "brain_id": "test",
        "rules": [
            {
                "category": "DRAFTING",
                "description": "Some rule with invalid type",
                "confidence": 0.90,
                "state": "RULE",
                "fire_count": 5,
                "correction_type": "nonexistent_type",
            },
        ],
        "rule_count": 1,
    }
    result = brain.absorb(package)
    assert result["absorbed"] == 1  # Should still absorb with default type
