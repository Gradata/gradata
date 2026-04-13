"""Tests for rule-to-hook graduation."""
from pathlib import Path

import pytest

from gradata.brain import Brain
from gradata.enhancements.rule_to_hook import (
    DeterminismCheck,
    EnforcementType,
    classify_rule,
    find_hook_candidates,
)


def test_correction_event_captures_draft_text(tmp_path: Path) -> None:
    """CORRECTION events must carry the raw violating assistant draft under
    ``data['draft_text']`` so later tasks can use it as ground truth when
    self-testing generated hooks."""
    brain = Brain.init(
        tmp_path / "brain",
        name="RuleToHookTest",
        domain="Testing",
        embedding="local",
        interactive=False,
    )

    brain.record_correction(
        text="no don't use em dashes",
        assistant_draft="Subject: Let me — help you out",
        category="FORMATTING",
    )

    events = brain.query_events(event_type="CORRECTION", last_n_sessions=1)
    assert len(events) == 1
    assert events[0]["data"]["draft_text"] == "Subject: Let me — help you out"
    assert events[0]["data"]["category"] == "FORMATTING"


class TestClassifyRule:
    def test_em_dash_rule_is_deterministic(self):
        result = classify_rule("Never use em dashes in prose", 0.95)
        assert result.determinism == DeterminismCheck.REGEX_PATTERN
        assert result.enforcement == EnforcementType.HOOK

    def test_file_size_rule_is_deterministic(self):
        result = classify_rule("Keep files under 500 lines", 0.92)
        assert result.determinism == DeterminismCheck.FILE_CHECK

    def test_secret_rule_is_deterministic(self):
        result = classify_rule("Never commit secrets or API keys", 0.98)
        assert result.determinism == DeterminismCheck.COMMAND_BLOCK

    def test_test_rule_is_deterministic(self):
        result = classify_rule("Run tests after code changes", 0.91)
        assert result.determinism == DeterminismCheck.TEST_TRIGGER

    def test_read_before_edit_is_deterministic(self):
        result = classify_rule("Always read a file before editing it", 0.93)
        assert result.determinism == DeterminismCheck.FILE_CHECK

    def test_destructive_command_is_deterministic(self):
        result = classify_rule("Never force push to main", 0.96)
        assert result.determinism == DeterminismCheck.COMMAND_BLOCK

    def test_tone_rule_is_not_deterministic(self):
        result = classify_rule("Be concise and direct", 0.91)
        assert result.determinism == DeterminismCheck.NOT_DETERMINISTIC
        assert result.enforcement == EnforcementType.PROMPT_INJECTION

    def test_judgment_rule_is_not_deterministic(self):
        result = classify_rule("Lead with the answer, not the reasoning", 0.90)
        assert result.determinism == DeterminismCheck.NOT_DETERMINISTIC

    def test_audience_rule_is_not_deterministic(self):
        result = classify_rule("Match formality to the audience", 0.92)
        assert result.determinism == DeterminismCheck.NOT_DETERMINISTIC


class TestFindHookCandidates:
    def test_filters_by_confidence(self):
        lessons = [
            {"status": "RULE", "confidence": 0.95, "description": "Never use em dashes"},
            {"status": "PATTERN", "confidence": 0.80, "description": "Never use em dashes"},
        ]
        candidates = find_hook_candidates(lessons, min_confidence=0.90)
        assert len(candidates) == 1

    def test_filters_by_status(self):
        lessons = [
            {"status": "RULE", "confidence": 0.95, "description": "Never use em dashes"},
            {"status": "INSTINCT", "confidence": 0.95, "description": "Never use em dashes"},
        ]
        candidates = find_hook_candidates(lessons)
        assert len(candidates) == 1

    def test_returns_only_deterministic(self):
        lessons = [
            {"status": "RULE", "confidence": 0.95, "description": "Never use em dashes"},
            {"status": "RULE", "confidence": 0.95, "description": "Be concise and direct"},
        ]
        candidates = find_hook_candidates(lessons)
        assert len(candidates) == 1
        assert candidates[0].determinism == DeterminismCheck.REGEX_PATTERN

    def test_empty_lessons(self):
        assert find_hook_candidates([]) == []

    def test_meta_rule_included(self):
        lessons = [
            {"status": "META_RULE", "confidence": 0.98, "description": "Run tests after code changes"},
        ]
        candidates = find_hook_candidates(lessons)
        assert len(candidates) == 1
