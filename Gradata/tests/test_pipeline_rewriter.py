"""Tests for Meta-Harness B pipeline_rewriter — read-only threshold proposer."""

from __future__ import annotations

from pathlib import Path

from gradata._types import Lesson, LessonState
from gradata.enhancements.pipeline_rewriter import (
    PipelineDiagnostic,
    ThresholdProposal,
    analyze_pipeline,
    run_pipeline_rewriter,
    write_adr,
)


def _mk_lesson(
    state: LessonState,
    *,
    category: str = "DRAFTING",
    description: str = "Example rule",
    confidence: float = 0.50,
    fire_count: int = 0,
) -> Lesson:
    return Lesson(
        date="2026-01-01",
        state=state,
        confidence=confidence,
        category=category,
        description=description,
        fire_count=fire_count,
    )


def test_analyze_empty_brain_produces_no_proposals():
    diag = analyze_pipeline([], [], [])
    assert diag.proposals == []
    assert diag.stuck_at_instinct == 0
    assert diag.over_promoted_rules == []
    assert any("healthy" in n for n in diag.notes)


def test_analyze_flags_stuck_at_instinct():
    """Many INSTINCTs with enough fires but confidence below PATTERN_THRESHOLD
    should propose a PATTERN_THRESHOLD drop."""
    lessons = [
        _mk_lesson(LessonState.INSTINCT, description=f"lesson {i}", confidence=0.55, fire_count=4)
        for i in range(8)
    ]
    diag = analyze_pipeline(lessons, [], [])
    assert diag.stuck_at_instinct == 8
    pattern_proposals = [p for p in diag.proposals if p.constant == "PATTERN_THRESHOLD"]
    assert len(pattern_proposals) == 1
    prop = pattern_proposals[0]
    assert prop.proposed < prop.current
    assert prop.evidence_count == 8


def test_analyze_flags_over_promoted_rules():
    """A RULE with failure_rate >= 30% should trigger a
    MIN_APPLICATIONS_FOR_RULE bump."""
    rule = _mk_lesson(
        LessonState.RULE,
        description="Don't attribute quotes prospects didn't say",
        confidence=0.92,
        fire_count=10,
    )
    failures = [
        {"data": {"failed_rule_description": rule.description}}
        for _ in range(5)  # 50% failure rate
    ]
    diag = analyze_pipeline([rule], failures, [])
    assert len(diag.over_promoted_rules) == 1
    assert diag.over_promoted_rules[0]["failure_rate"] == 0.5
    bumps = [p for p in diag.proposals if p.constant == "MIN_APPLICATIONS_FOR_RULE"]
    assert len(bumps) == 1
    assert bumps[0].proposed > bumps[0].current


def test_analyze_accepts_hook_emitted_failure_shape():
    """capture_learning.py emits {data: {description: ...}} (no prefix).
    self_healing emits {data: {failed_rule_description: ...}}. Both count."""
    rule = _mk_lesson(
        LessonState.RULE,
        description="shared rule",
        confidence=0.92,
        fire_count=4,
    )
    failures = [
        {"data": {"description": "shared rule"}},
        {"data": {"failed_rule_description": "shared rule"}},
    ]
    diag = analyze_pipeline([rule], failures, [])
    # failure_count=2, fire_count=4 → 50% ≥ 30% threshold
    assert len(diag.over_promoted_rules) == 1
    assert diag.over_promoted_rules[0]["failure_count"] == 2


def test_analyze_flags_zero_rules_in_populated_brain():
    """A brain with many lessons but zero RULEs → suggest lowering
    MIN_APPLICATIONS_FOR_RULE."""
    lessons = [
        _mk_lesson(LessonState.PATTERN, description=f"p{i}", confidence=0.75, fire_count=4)
        for i in range(25)
    ]
    diag = analyze_pipeline(lessons, [], [])
    drops = [
        p
        for p in diag.proposals
        if p.constant == "MIN_APPLICATIONS_FOR_RULE" and p.proposed < p.current
    ]
    assert len(drops) == 1


def test_write_adr_produces_readable_markdown(tmp_path: Path):
    diag = PipelineDiagnostic(
        population={"RULE": 1, "PATTERN": 3, "INSTINCT": 9},
        stuck_at_instinct=6,
        rule_failure_count=4,
        proposals=[
            ThresholdProposal(
                constant="PATTERN_THRESHOLD",
                current=0.60,
                proposed=0.55,
                evidence_count=6,
                rationale="Many INSTINCTs stuck.",
            ),
        ],
    )
    path = write_adr(diag, tmp_path)
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "Pipeline threshold proposals" in text
    assert "PATTERN_THRESHOLD" in text
    assert "0.6" in text and "0.55" in text
    assert "Many INSTINCTs stuck" in text


def test_write_adr_healthy_brain_notes_no_action(tmp_path: Path):
    diag = analyze_pipeline([], [], [])
    path = write_adr(diag, tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "_None" in text  # healthy-path marker in markdown
    assert "healthy" in text


def test_run_pipeline_rewriter_handles_missing_query_events(tmp_path: Path):
    """Brain without query_events must not crash — fall back to empty events."""

    class DummyBrain:
        def __init__(self) -> None:
            self.all_lessons = [_mk_lesson(LessonState.RULE, confidence=0.95, fire_count=6)]

    path = run_pipeline_rewriter(DummyBrain(), tmp_path)
    assert path.is_file()


def test_run_pipeline_rewriter_invokes_query_events(tmp_path: Path):
    calls: list[str] = []

    class FakeBrain:
        @property
        def all_lessons(self):
            return []

        def query_events(self, event_type: str, limit: int = 100):
            calls.append(event_type)
            _ = limit
            return []

    run_pipeline_rewriter(FakeBrain(), tmp_path)
    assert "RULE_FAILURE" in calls
    assert "CORRECTION" in calls


def test_proposal_delta_property():
    p = ThresholdProposal(
        constant="MIN_APPLICATIONS_FOR_RULE",
        current=5.0,
        proposed=6.0,
        evidence_count=3,
        rationale="x",
    )
    assert p.delta == 1.0
    n = ThresholdProposal(
        constant="PATTERN_THRESHOLD",
        current=0.60,
        proposed=0.55,
        evidence_count=1,
        rationale="x",
    )
    assert n.delta == -0.05
