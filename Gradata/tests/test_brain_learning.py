"""
Tests for BrainLearningMixin — focused on detect_implicit_feedback() and forget().

Also covers correct() input validation, log_output(), plan(), and spawn_queue()
at the behavioral level (no internal state inspection).

Run: cd sdk && python -m pytest tests/test_brain_learning.py -v
"""

from __future__ import annotations

import pytest

from tests.conftest import init_brain

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_lessons(brain, n: int = 1, category: str = "TONE") -> None:
    """Create or append minimal lessons.md entries so forget() has something to remove.

    Uses format_lessons() to guarantee the file is parseable by parse_lessons().
    Appends to an existing file so multiple calls accumulate lessons.
    """
    from datetime import date

    from gradata._types import Lesson, LessonState
    from gradata.enhancements.self_improvement import format_lessons, parse_lessons

    new_lessons = [
        Lesson(
            date=date.today().isoformat(),
            state=LessonState.INSTINCT,
            confidence=0.40,
            category=category,
            description=f"lesson {i}: always do the thing",
        )
        for i in range(n)
    ]

    # _find_lessons_path() checks brain.dir / "lessons.md" first
    lessons_path = brain.dir / "lessons.md"

    # Preserve any lessons already written (multi-call safety)
    existing: list = []
    if lessons_path.exists():
        existing = parse_lessons(lessons_path.read_text(encoding="utf-8"))

    lessons_path.write_text(format_lessons(existing + new_lessons), encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. detect_implicit_feedback()
# ---------------------------------------------------------------------------


class TestDetectImplicitFeedback:
    """detect_implicit_feedback() classifies implicit signals in user text."""

    # --- happy path: each signal type ---

    def test_detects_pushback(self, fresh_brain):
        result = fresh_brain.detect_implicit_feedback("Are you sure that's correct?")
        assert result["has_feedback"] is True
        signal_types = [s["type"] for s in result["signals"]]
        assert "pushback" in signal_types

    def test_detects_reminder(self, fresh_brain):
        result = fresh_brain.detect_implicit_feedback("Make sure you include the pricing.")
        assert result["has_feedback"] is True
        signal_types = [s["type"] for s in result["signals"]]
        assert "reminder" in signal_types

    def test_detects_gap(self, fresh_brain):
        result = fresh_brain.detect_implicit_feedback("What about the appendix section?")
        assert result["has_feedback"] is True
        signal_types = [s["type"] for s in result["signals"]]
        assert "gap" in signal_types

    def test_detects_challenge(self, fresh_brain):
        result = fresh_brain.detect_implicit_feedback("I feel like this isn't complete.")
        assert result["has_feedback"] is True
        signal_types = [s["type"] for s in result["signals"]]
        assert "challenge" in signal_types

    # --- return structure ---

    def test_returns_required_keys(self, fresh_brain):
        result = fresh_brain.detect_implicit_feedback("hello")
        for key in ("signals", "has_feedback", "event"):
            assert key in result

    def test_signals_is_list(self, fresh_brain):
        result = fresh_brain.detect_implicit_feedback("are you sure?")
        assert isinstance(result["signals"], list)

    def test_has_feedback_is_bool(self, fresh_brain):
        result = fresh_brain.detect_implicit_feedback("are you sure?")
        assert isinstance(result["has_feedback"], bool)

    def test_event_emitted_when_feedback_detected(self, fresh_brain):
        result = fresh_brain.detect_implicit_feedback("don't forget the summary")
        assert result["event"] is not None
        assert result["event"]["type"] == "IMPLICIT_FEEDBACK"

    # --- no feedback ---

    def test_neutral_message_has_no_feedback(self, fresh_brain):
        result = fresh_brain.detect_implicit_feedback("Please draft an email to the client.")
        assert result["has_feedback"] is False
        assert result["signals"] == []
        assert result["event"] is None

    # --- edge cases ---

    def test_empty_string_has_no_feedback(self, fresh_brain):
        result = fresh_brain.detect_implicit_feedback("")
        assert result["has_feedback"] is False
        assert result["signals"] == []

    def test_case_insensitive_detection(self, fresh_brain):
        result = fresh_brain.detect_implicit_feedback("ARE YOU SURE about this?")
        assert result["has_feedback"] is True

    def test_multiple_signals_all_captured(self, fresh_brain):
        msg = "Are you sure? Don't forget the pricing. What about the intro?"
        result = fresh_brain.detect_implicit_feedback(msg)
        types = {s["type"] for s in result["signals"]}
        assert len(types) >= 2

    def test_each_signal_has_type_and_marker(self, fresh_brain):
        result = fresh_brain.detect_implicit_feedback("you forgot the header section")
        for signal in result["signals"]:
            assert "type" in signal
            assert "marker" in signal

    def test_explicit_session_stored_in_event(self, fresh_brain):
        result = fresh_brain.detect_implicit_feedback("why did you skip this?", session=42)
        assert result["event"]["session"] == 42

    def test_very_long_message_does_not_raise(self, fresh_brain):
        long_msg = "are you sure " + "x " * 5000
        result = fresh_brain.detect_implicit_feedback(long_msg)
        assert result["has_feedback"] is True

    def test_special_characters_do_not_cause_errors(self, fresh_brain):
        result = fresh_brain.detect_implicit_feedback("are you sure? <>&\"'")
        assert result["has_feedback"] is True


# ---------------------------------------------------------------------------
# 2. forget()
# ---------------------------------------------------------------------------


class TestForget:
    """forget() — human-friendly undo via plain English strings."""

    def test_forget_last_no_lessons(self, fresh_brain):
        result = fresh_brain.forget("last")
        assert result.get("forgot") is False or result.get("rolled_back") is False

    def test_forget_last_kills_most_recent(self, tmp_path):
        brain = init_brain(tmp_path)
        _seed_lessons(brain, n=3, category="TONE")
        result = brain.forget("last")
        assert result.get("rolled_back") is True

    def test_forget_last_n(self, tmp_path):
        brain = init_brain(tmp_path)
        _seed_lessons(brain, n=3, category="TONE")
        results = brain.forget("last 2")
        assert isinstance(results, list)
        assert len(results) == 2

    def test_forget_by_description_fuzzy(self, tmp_path):
        brain = init_brain(tmp_path)
        _seed_lessons(brain, n=3, category="TONE")
        result = brain.forget("lesson 1")
        assert result.get("rolled_back") is True

    def test_forget_all_category(self, tmp_path):
        brain = init_brain(tmp_path)
        _seed_lessons(brain, n=3, category="TONE")
        results = brain.forget("all TONE")
        if isinstance(results, list):
            assert len(results) == 3
        else:
            assert results.get("rolled_back") is True

    def test_forget_all_category_case_insensitive(self, tmp_path):
        brain = init_brain(tmp_path)
        _seed_lessons(brain, n=1, category="TONE")
        result = brain.forget("all tone")
        if isinstance(result, dict):
            assert result.get("rolled_back") is True

    def test_forget_no_match_returns_error(self, tmp_path):
        brain = init_brain(tmp_path)
        _seed_lessons(brain, n=2, category="TONE")
        result = brain.forget("this description does not exist xyz999")
        assert result.get("rolled_back") is False

    def test_forget_defaults_to_last(self, tmp_path):
        brain = init_brain(tmp_path)
        _seed_lessons(brain, n=2, category="TONE")
        result = brain.forget()
        assert result.get("rolled_back") is True


# ---------------------------------------------------------------------------
# 3. correct() — input validation (guard-rails, not pipeline internals)
# ---------------------------------------------------------------------------


class TestCorrectValidation:
    """correct() rejects malformed inputs before touching the pipeline."""

    def test_raises_when_both_empty(self, fresh_brain):
        with pytest.raises(ValueError, match="empty"):
            fresh_brain.correct("", "")

    def test_raises_when_identical(self, fresh_brain):
        with pytest.raises(ValueError, match="identical"):
            fresh_brain.correct("same text", "same text")

    def test_raises_when_combined_length_exceeds_limit(self, fresh_brain):
        # draft and final must be different (not identical) to reach the length check
        draft = "x" * 60_000
        final = "y" * 60_000
        with pytest.raises(ValueError, match="exceeds"):
            fresh_brain.correct(draft, final)

    def test_raises_for_invalid_session_zero(self, fresh_brain):
        with pytest.raises(ValueError, match="session"):
            fresh_brain.correct("draft", "final", session=0)

    def test_raises_for_negative_session(self, fresh_brain):
        with pytest.raises(ValueError, match="session"):
            fresh_brain.correct("draft", "final", session=-1)

    def test_raises_for_string_session(self, fresh_brain):
        with pytest.raises((ValueError, TypeError)):
            fresh_brain.correct("draft", "final", session="abc")

    def test_happy_path_returns_dict(self, fresh_brain):
        result = fresh_brain.correct("draft text here", "final text here")
        assert isinstance(result, dict)
        assert result.get("type") == "CORRECTION"

    def test_category_override_stored(self, fresh_brain):
        result = fresh_brain.correct("old version", "new version", category="TONE")
        assert result["data"]["category"] == "TONE"


# ---------------------------------------------------------------------------
# 4. log_output()
# ---------------------------------------------------------------------------


class TestLogOutput:
    """log_output() records AI-generated text for outcome attribution."""

    def test_returns_event_dict(self, fresh_brain):
        result = fresh_brain.log_output("some output text")
        assert isinstance(result, dict)
        assert result["type"] == "OUTPUT"

    def test_output_type_defaults_to_general(self, fresh_brain):
        result = fresh_brain.log_output("text")
        assert result["data"]["output_type"] == "general"

    def test_custom_output_type_stored(self, fresh_brain):
        result = fresh_brain.log_output("text", output_type="email")
        assert result["data"]["output_type"] == "email"

    def test_self_score_stored_when_provided(self, fresh_brain):
        result = fresh_brain.log_output("text", self_score=9.5)
        assert result["data"]["self_score"] == 9.5

    def test_text_truncated_to_5000_chars(self, fresh_brain):
        long_text = "a" * 10_000
        result = fresh_brain.log_output(long_text)
        assert len(result["data"]["output_text"]) <= 5000

    def test_empty_text_accepted(self, fresh_brain):
        result = fresh_brain.log_output("")
        assert result["type"] == "OUTPUT"

    def test_rules_applied_stored(self, fresh_brain):
        result = fresh_brain.log_output("text", rules_applied=["rule_a", "rule_b"])
        assert "rule_a" in result["data"]["rules_applied"]


# ---------------------------------------------------------------------------
# 5. plan()
# ---------------------------------------------------------------------------


class TestPlan:
    """plan() builds a structured task plan (steps + applicable rules)."""

    def test_returns_dict(self, fresh_brain):
        result = fresh_brain.plan("write an email")
        assert isinstance(result, dict)

    def test_plan_contains_task(self, fresh_brain):
        result = fresh_brain.plan("write an email")
        assert result["task"] == "write an email"

    def test_plan_has_steps_list(self, fresh_brain):
        result = fresh_brain.plan("do something")
        assert isinstance(result["steps"], list)
        assert len(result["steps"]) >= 1

    def test_plan_has_rules_count(self, fresh_brain):
        result = fresh_brain.plan("do something")
        assert "rules_count" in result
        assert isinstance(result["rules_count"], int)

    def test_plan_passes_context_through(self, fresh_brain):
        result = fresh_brain.plan("task", context={"domain": "sales"})
        assert result["context"]["domain"] == "sales"

    def test_plan_with_empty_task(self, fresh_brain):
        result = fresh_brain.plan("")
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# 6. spawn_queue()
# ---------------------------------------------------------------------------


class TestSpawnQueue:
    """spawn_queue() runs tasks concurrently and returns completion stats."""

    def test_returns_dict_with_summary_keys(self, fresh_brain):
        result = fresh_brain.spawn_queue(["a", "b"], worker=lambda t: {"done": t})
        for key in ("total", "completed", "failed", "results", "failures"):
            assert key in result

    def test_total_equals_input_count(self, fresh_brain):
        result = fresh_brain.spawn_queue(["a", "b", "c"], worker=lambda t: {})
        assert result["total"] == 3

    def test_successful_workers_counted(self, fresh_brain):
        result = fresh_brain.spawn_queue(["a", "b"], worker=lambda t: {"ok": True})
        assert result["completed"] == 2
        assert result["failed"] == 0

    def test_failing_worker_counted_as_failed(self, fresh_brain):
        def boom(t):
            raise RuntimeError("worker failed")

        result = fresh_brain.spawn_queue(["x"], worker=boom)
        assert result["failed"] == 1
        assert result["completed"] == 0

    def test_empty_task_list_returns_zero_totals(self, fresh_brain):
        result = fresh_brain.spawn_queue([], worker=lambda t: {})
        assert result["total"] == 0
        assert result["completed"] == 0

    def test_results_contain_task_field(self, fresh_brain):
        tasks = ["alpha", "beta"]
        result = fresh_brain.spawn_queue(tasks, worker=lambda t: {"t": t})
        for r in result["results"]:
            assert "task" in r

    def test_on_complete_callback_called(self, fresh_brain):
        calls = []
        fresh_brain.spawn_queue(
            ["task1"],
            worker=lambda t: {"t": t},
            on_complete=lambda r: calls.append(r),
        )
        assert len(calls) == 1

    def test_max_concurrent_does_not_raise(self, fresh_brain):
        """max_concurrent is accepted as a kwarg without blowing up."""
        result = fresh_brain.spawn_queue(
            ["a", "b", "c", "d"],
            worker=lambda t: {},
            max_concurrent=2,
        )
        assert result["total"] == 4
