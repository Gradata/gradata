"""
Tests for the closed learning loop and security fixes.
=======================================================
The most important tests in the entire SDK:
1. Full loop: correct() → lesson in lessons.md → rules available
2. PII sanitization in observation hooks
3. Q-table HMAC integrity
4. Auto-correct hook covers Edit + Write
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from gradata.enhancements.observation_hooks import observe_tool_use
from gradata.patterns.q_learning_router import QLearningRouter


# ===========================================================================
# THE MOST IMPORTANT TEST: Full Learning Loop End-to-End
# ===========================================================================


class TestFullLearningLoop:
    """Proves: correct() → lesson created → apply_brain_rules() returns it."""

    def test_correction_creates_lesson(self):
        """correct() with 2+ similar edits → lesson appears in lessons.md."""
        from gradata.brain import Brain

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            brain = Brain.init(tmpdir, domain="Test")

            brain.correct(
                draft="Dear Sir or Madam, I am writing to inform you about our product.",
                final="Hey, just wanted to let you know about what we built.",
                category="TONE",
            )
            brain.correct(
                draft="Dear Valued Customer, we are pleased to announce",
                final="Hey, we just shipped something cool",
                category="TONE",
            )

            lessons_path = brain.dir / "lessons.md"
            assert lessons_path.exists(), "lessons.md was not created"
            content = lessons_path.read_text(encoding="utf-8")
            assert content.strip() != "", "lessons.md is empty, loop is broken"

            from gradata.enhancements.self_improvement import parse_lessons
            lessons = parse_lessons(content)
            assert len(lessons) > 0, f"No lessons parsed from: {content[:200]}"

            tone_lessons = [l for l in lessons if l.category == "TONE"]
            assert len(tone_lessons) > 0, (
                f"No TONE lessons found. Categories: {[l.category for l in lessons]}"
            )

    def test_repeated_corrections_update_lessons(self):
        """More corrections in same category should update lessons.md."""
        from gradata.brain import Brain

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            brain = Brain.init(tmpdir, domain="Test")

            brain.correct(
                draft="We are delighted to present our findings",
                final="Here are the results",
                category="TONE",
            )
            brain.correct(
                draft="It is with great pleasure that we inform you",
                final="Quick update:",
                category="TONE",
            )

            from gradata.enhancements.self_improvement import parse_lessons
            content = (brain.dir / "lessons.md").read_text(encoding="utf-8")
            assert len(parse_lessons(content)) > 0

            brain.correct(
                draft="I would like to formally request your attendance",
                final="Can you join us?",
                category="TONE",
            )
            brain.correct(
                draft="Please be advised that the meeting has been rescheduled",
                final="Meeting moved to Tuesday",
                category="TONE",
            )

            content2 = (brain.dir / "lessons.md").read_text(encoding="utf-8")
            assert content2.strip() != ""

    def test_correct_event_has_lesson_signal(self):
        """Return value from correct() should indicate learning happened."""
        from gradata.brain import Brain

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            brain = Brain.init(tmpdir, domain="Test")
            brain.correct(
                draft="Dear Sir, I wish to formally complain",
                final="Hey, this is broken",
                category="STYLE",
            )
            event = brain.correct(
                draft="Esteemed colleague, please find attached",
                final="Here is the file",
                category="STYLE",
            )
            has_signal = (
                event.get("lessons_created", 0) > 0
                or event.get("lessons_updated", False)
                or event.get("patterns_extracted", 0) > 0
            )
            assert has_signal, f"No lesson signal. Keys: {list(event.keys())}"

    def test_full_roundtrip_correct_graduate_rules(self):
        """THE critical test: correct() → end_session() promotes → apply_brain_rules() returns rules."""
        from gradata.brain import Brain
        from gradata.enhancements.self_improvement import (
            parse_lessons, format_lessons, LessonState,
        )

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            brain = Brain.init(tmpdir, domain="Test")

            # Phase 1: Create corrections to generate a lesson
            for i in range(3):
                brain.correct(
                    draft=f"Dear Sir or Madam, I am writing regarding item {i}",
                    final=f"Hey, quick note about item {i}",
                    category="TONE",
                )

            lessons_path = brain.dir / "lessons.md"
            assert lessons_path.exists(), "lessons.md not created"

            lessons = parse_lessons(lessons_path.read_text(encoding="utf-8"))
            assert len(lessons) > 0, "No lessons created from corrections"

            # Phase 2: Manually promote a lesson to PATTERN (simulates surviving sessions)
            # In production this happens over many sessions via end_session().
            # Here we set it directly to verify the downstream path works.
            for lesson in lessons:
                lesson.state = LessonState.PATTERN
                lesson.confidence = 0.65
                lesson.fire_count = 5

            lessons_path.write_text(format_lessons(lessons), encoding="utf-8")

            # Phase 3: Verify apply_brain_rules() returns the promoted lesson
            rules = brain.apply_brain_rules("writing an email to a prospect")
            assert rules.strip() != "", (
                f"apply_brain_rules() returned empty string. "
                f"Lessons: {[(l.state.value, l.confidence, l.category) for l in lessons]}"
            )
            assert "TONE" in rules or "tone" in rules.lower(), (
                f"TONE lesson not found in rules output: {rules[:200]}"
            )

    def test_end_session_promotes_lessons(self):
        """end_session() should bump confidence on surviving lessons."""
        from gradata.brain import Brain
        from gradata.enhancements.self_improvement import (
            parse_lessons, format_lessons, LessonState,
        )

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            brain = Brain.init(tmpdir, domain="Test")

            # Create lessons via corrections (use valid category)
            for i in range(3):
                brain.correct(
                    draft=f"We are pleased to inform you about update {i}",
                    final=f"Here is update {i}",
                    category="TONE",
                )

            lessons_path = brain.dir / "lessons.md"
            lessons = parse_lessons(lessons_path.read_text(encoding="utf-8"))
            assert len(lessons) > 0

            # Give lessons enough fire_count to survive graduation
            # (otherwise end_session kills low-activity lessons)
            for lesson in lessons:
                lesson.fire_count = 3
                lesson.confidence = 0.30  # INSTINCT — should get bumped

            conf_before = [l.confidence for l in lessons]
            lessons_path.write_text(format_lessons(lessons), encoding="utf-8")

            # Run end_session with corrections in OTHER categories
            # — TONE lesson survives (no TONE corrections) → confidence bumps
            result = brain.end_session(session_corrections=[
                {"category": "ACCURACY", "severity": "minor"},
            ])

            text_after = lessons_path.read_text(encoding="utf-8")
            lessons_after = parse_lessons(text_after)
            conf_after = [l.confidence for l in lessons_after]

            # Lessons should either be promoted or have higher confidence
            has_progress = (
                any(a > b for a, b in zip(conf_after, conf_before))
                or result.get("promotions", 0) > 0
                or result.get("graduated", 0) > 0
            )
            assert has_progress, (
                f"end_session() showed no progress. "
                f"Before: {conf_before}, After: {conf_after}, Result: {result}"
            )

    def test_export_rules_produces_markdown(self):
        """export_rules() returns portable markdown with graduated rules."""
        from gradata.brain import Brain
        from gradata.enhancements.self_improvement import (
            parse_lessons, format_lessons, LessonState,
        )

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            brain = Brain.init(tmpdir, domain="Test")

            # Create a lesson and force it to PATTERN state
            brain.correct(
                draft="Dear Sir or Madam, I am writing to formally inform you",
                final="Hey, just wanted to let you know",
                category="TONE",
            )
            lessons_path = brain.dir / "lessons.md"
            lessons = parse_lessons(lessons_path.read_text(encoding="utf-8"))
            for l in lessons:
                l.state = LessonState.PATTERN
                l.confidence = 0.75
                l.fire_count = 5
            lessons_path.write_text(format_lessons(lessons), encoding="utf-8")

            # Export
            result = brain.export_rules(min_state="PATTERN")
            assert "# Brain Rules Export" in result
            assert "TONE" in result
            assert "PATTERN:75%" in result

    def test_export_rules_empty_for_instinct_only(self):
        """export_rules() returns empty when only INSTINCT lessons exist."""
        from gradata.brain import Brain

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            brain = Brain.init(tmpdir, domain="Test")
            brain.correct(
                draft="formal text", final="casual text", category="TONE",
            )
            result = brain.export_rules(min_state="PATTERN")
            assert result == ""

    def test_lineage_tracks_state_transitions(self):
        """lineage() returns state transition history after graduation."""
        from gradata.brain import Brain
        from gradata.enhancements.self_improvement import (
            parse_lessons, format_lessons, LessonState,
        )

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            brain = Brain.init(tmpdir, domain="Test")

            # Create a lesson and force promotion
            brain.correct(
                draft="We are pleased to inform you",
                final="Hey, here's the update",
                category="TONE",
            )
            lessons_path = brain.dir / "lessons.md"
            lessons = parse_lessons(lessons_path.read_text(encoding="utf-8"))
            for l in lessons:
                l.confidence = 0.65
                l.fire_count = 4
            lessons_path.write_text(format_lessons(lessons), encoding="utf-8")

            # Graduate — should promote INSTINCT -> PATTERN
            brain.end_session(session_corrections=[], session_type="full")

            # Check lineage
            transitions = brain.lineage()
            assert len(transitions) > 0, "No transitions logged"
            assert transitions[0]["old_state"] == "INSTINCT"
            assert transitions[0]["new_state"] == "PATTERN"
            assert transitions[0]["category"] == "TONE"

    def test_lineage_empty_for_new_brain(self):
        """lineage() returns empty list for a brain with no graduations."""
        from gradata.brain import Brain

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            brain = Brain.init(tmpdir, domain="Test")
            assert brain.lineage() == []

    def test_correct_with_agent_type_creates_scoped_lesson(self):
        """correct(agent_type=...) stores agent_type on the lesson."""
        from gradata.brain import Brain
        from gradata.enhancements.self_improvement import parse_lessons

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            brain = Brain.init(tmpdir, domain="Test")
            brain.correct(
                draft="The system uses global mutable state",
                final="The system uses dependency injection",
                category="ARCHITECTURE",
                agent_type="code-reviewer",
            )
            lessons_path = brain.dir / "lessons.md"
            lessons = parse_lessons(lessons_path.read_text(encoding="utf-8"))
            agent_lessons = [l for l in lessons if l.agent_type == "code-reviewer"]
            assert len(agent_lessons) > 0, (
                f"No agent-typed lessons found. Types: {[l.agent_type for l in lessons]}"
            )

    def test_agent_profile_returns_skills(self):
        """agent_profile() returns correction categories and skill state."""
        from gradata.brain import Brain
        from gradata.enhancements.self_improvement import parse_lessons, format_lessons
        from gradata._types import LessonState

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            brain = Brain.init(tmpdir, domain="Test")
            brain.correct(
                draft="formal text", final="casual text",
                category="TONE", agent_type="email-drafter",
            )
            # Force one lesson to PATTERN
            lessons_path = brain.dir / "lessons.md"
            lessons = parse_lessons(lessons_path.read_text(encoding="utf-8"))
            for l in lessons:
                if l.agent_type == "email-drafter":
                    l.state = LessonState.PATTERN
                    l.confidence = 0.75
                    l.fire_count = 5
            lessons_path.write_text(format_lessons(lessons), encoding="utf-8")

            profile = brain.agent_profile("email-drafter")
            assert profile["agent_type"] == "email-drafter"
            assert profile["total_lessons"] > 0
            assert len(profile["skills_acquired"]) > 0
            assert profile["skills_acquired"][0]["category"] == "TONE"

    def test_agent_profile_empty_for_unknown_agent(self):
        """agent_profile() returns 0 lessons for unknown agent type."""
        from gradata.brain import Brain

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            brain = Brain.init(tmpdir, domain="Test")
            profile = brain.agent_profile("nonexistent")
            assert profile["total_lessons"] == 0


# ===========================================================================
# PII Sanitization
# ===========================================================================


class TestPIISanitization:

    def test_email_redacted(self):
        obs = observe_tool_use("Test", input_data="Send to user@example.com please")
        assert "user@example.com" not in obs.input_summary
        assert "[EMAIL]" in obs.input_summary

    def test_clean_text_unchanged(self):
        obs = observe_tool_use("Test", input_data="Just a normal command")
        assert obs.input_summary == "Just a normal command"

    def test_token_pattern_redacted(self):
        obs = observe_tool_use("Test", input_data="bearer AAAAAAAAAAAAAAAA")
        assert "AAAAAAAAAAAAAAAA" not in obs.input_summary
        assert "[TOKEN]" in obs.input_summary


# ===========================================================================
# Q-Table HMAC Integrity
# ===========================================================================


class TestQTableIntegrity:

    def test_save_load_with_hmac(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fp = Path(tmpdir) / "router.json"
            r = QLearningRouter()
            d = r.route("test")
            r.update_reward(d, 0.8)
            r.save(fp)

            r2 = QLearningRouter()
            assert r2.load(fp) is True
            assert r2.update_count == 1

    def test_tampered_file_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fp = Path(tmpdir) / "router.json"
            r = QLearningRouter()
            r.save(fp)

            data = json.loads(fp.read_text())
            data["epsilon"] = 0.0
            fp.write_text(json.dumps(data))

            r2 = QLearningRouter()
            assert r2.load(fp) is False

    def test_legacy_no_hmac_still_loads(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fp = Path(tmpdir) / "router.json"
            fp.write_text(json.dumps({
                "version": "1.0.0",
                "q_table": {},
                "epsilon": 0.5,
                "update_count": 10,
                "stats": {},
            }))
            r = QLearningRouter()
            assert r.load(fp) is True


# ===========================================================================
# Auto-Correct Hook
# ===========================================================================


class TestAutoCorrectHookCoverage:

    def test_hook_matches_edit_and_write(self):
        from gradata.hooks.auto_correct import generate_hook_config
        config = generate_hook_config()
        matchers = [h["matcher"] for h in config["hooks"]["PostToolUse"]]
        assert "Edit" in matchers
        assert "Write" in matchers
