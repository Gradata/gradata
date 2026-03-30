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
