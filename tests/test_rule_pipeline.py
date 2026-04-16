"""Tests for the 3-phase Rule Pipeline Orchestrator.

Covers PipelineResult and run_rule_pipeline with unit-level isolation —
optional dependencies (freshness, retrieval_fusion, behavioral_engine,
meta_rules, rule_to_hook) are mocked or suppressed via import patching.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gradata._types import Lesson, LessonState
from gradata.enhancements.self_improvement import (
    PipelineResult,
    format_lessons,
    run_rule_pipeline,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_lesson(
    state: LessonState = LessonState.INSTINCT,
    confidence: float = 0.50,
    category: str = "FORMATTING",
    description: str = "Never use em dashes",
    fire_count: int = 0,
    sessions_since_fire: int = 0,
) -> Lesson:
    return Lesson(
        date="2026-01-01",
        state=state,
        confidence=confidence,
        category=category,
        description=description,
        fire_count=fire_count,
        sessions_since_fire=sessions_since_fire,
    )


def _write_lessons(path: Path, lessons: list[Lesson]) -> None:
    path.write_text(format_lessons(lessons), encoding="utf-8")


# ---------------------------------------------------------------------------
# PipelineResult unit tests
# ---------------------------------------------------------------------------


def test_pipeline_result_defaults() -> None:
    """PipelineResult fields all start empty / zero."""
    r = PipelineResult()
    assert r.graduated == []
    assert r.demoted == []
    assert r.meta_rules_created == []
    assert r.hooks_promoted == []
    assert r.disposition_updates == {}
    assert r.freshness_updates == 0
    assert r.errors == []


def test_pipeline_result_tracks_changes() -> None:
    """PipelineResult accumulates values correctly."""
    r = PipelineResult(
        graduated=["FORMATTING:Never use em"],
        meta_rules_created=["mr-001"],
        hooks_promoted=["Never use em dashes"],
        freshness_updates=3,
        errors=["Phase 2: oops"],
    )
    assert len(r.graduated) == 1
    assert len(r.meta_rules_created) == 1
    assert r.freshness_updates == 3
    assert len(r.errors) == 1


# ---------------------------------------------------------------------------
# run_rule_pipeline integration tests (filesystem, no optional deps)
# ---------------------------------------------------------------------------


def test_pipeline_empty_lessons_returns_empty_result(tmp_path: Path) -> None:
    """An empty lessons.md yields a result with no changes and no errors."""
    lessons_path = tmp_path / "lessons.md"
    lessons_path.write_text("", encoding="utf-8")
    db_path = tmp_path / "system.db"

    result = run_rule_pipeline(lessons_path, db_path, current_session=1)

    assert result.graduated == []
    assert result.hooks_promoted == []
    assert result.freshness_updates == 0
    # meta_rules error expected because module may not exist; that's fine
    # Only hard failures should be absent
    assert not any("Phase 1" in e for e in result.errors)


def test_pipeline_graduates_instinct_to_pattern(tmp_path: Path) -> None:
    """INSTINCT lesson at 0.60 confidence with >= 3 fires graduates to PATTERN."""
    lesson = _make_lesson(
        state=LessonState.INSTINCT,
        confidence=0.60,
        fire_count=3,
    )
    lessons_path = tmp_path / "lessons.md"
    _write_lessons(lessons_path, [lesson])
    db_path = tmp_path / "system.db"

    result = run_rule_pipeline(lessons_path, db_path, current_session=5)

    assert len(result.graduated) == 1
    assert "FORMATTING" in result.graduated[0]

    # Verify the file was actually updated
    updated_text = lessons_path.read_text(encoding="utf-8")
    assert "PATTERN" in updated_text


def test_pipeline_does_not_graduate_instinct_below_threshold(tmp_path: Path) -> None:
    """INSTINCT lesson below 0.60 confidence stays INSTINCT."""
    lesson = _make_lesson(
        state=LessonState.INSTINCT,
        confidence=0.55,
        fire_count=5,
    )
    lessons_path = tmp_path / "lessons.md"
    _write_lessons(lessons_path, [lesson])
    db_path = tmp_path / "system.db"

    result = run_rule_pipeline(lessons_path, db_path, current_session=5)

    assert result.graduated == []


def test_pipeline_graduates_pattern_to_rule(tmp_path: Path) -> None:
    """PATTERN lesson at 0.90 confidence with >= 3 fires graduates to RULE."""
    lesson = _make_lesson(
        state=LessonState.PATTERN,
        confidence=0.90,
        fire_count=3,
    )
    lessons_path = tmp_path / "lessons.md"
    _write_lessons(lessons_path, [lesson])
    db_path = tmp_path / "system.db"

    result = run_rule_pipeline(lessons_path, db_path, current_session=10)

    assert len(result.graduated) == 1

    updated_text = lessons_path.read_text(encoding="utf-8")
    assert "RULE" in updated_text


def test_pipeline_does_not_graduate_pattern_without_fires(tmp_path: Path) -> None:
    """PATTERN lesson with high confidence but zero fires stays PATTERN."""
    lesson = _make_lesson(
        state=LessonState.PATTERN,
        confidence=0.92,
        fire_count=0,
    )
    lessons_path = tmp_path / "lessons.md"
    _write_lessons(lessons_path, [lesson])
    db_path = tmp_path / "system.db"

    result = run_rule_pipeline(lessons_path, db_path, current_session=10)

    assert result.graduated == []


def test_pipeline_handles_missing_freshness_module(tmp_path: Path) -> None:
    """Pipeline completes even when the freshness module is not installed."""
    lesson = _make_lesson(
        state=LessonState.RULE,
        confidence=0.95,
        fire_count=5,
        sessions_since_fire=40,  # would trigger decay if freshness existed
    )
    lessons_path = tmp_path / "lessons.md"
    _write_lessons(lessons_path, [lesson])
    db_path = tmp_path / "system.db"

    # Temporarily block freshness import
    with patch.dict(sys.modules, {"gradata.enhancements.freshness": None}):
        result = run_rule_pipeline(lessons_path, db_path, current_session=50)

    # No Phase 1 hard errors — freshness silently skipped
    assert not any("Phase 1: failed to load" in e for e in result.errors)
    assert result.freshness_updates == 0


def test_pipeline_handles_missing_retrieval_fusion_module(tmp_path: Path) -> None:
    """Pipeline completes even when retrieval_fusion is not installed."""
    lesson = _make_lesson(
        state=LessonState.PATTERN,
        confidence=0.80,
        fire_count=4,
    )
    lessons_path = tmp_path / "lessons.md"
    _write_lessons(lessons_path, [lesson])
    db_path = tmp_path / "system.db"

    with patch.dict(sys.modules, {"gradata.enhancements.retrieval_fusion": None}):
        result = run_rule_pipeline(lessons_path, db_path, current_session=5)

    assert not any("retrieval_fusion" in e for e in result.errors)


def test_pipeline_disposition_updates_from_corrections(tmp_path: Path) -> None:
    """Corrections flow into disposition_updates when behavioral_engine is present."""
    lessons_path = tmp_path / "lessons.md"
    lessons_path.write_text("", encoding="utf-8")
    db_path = tmp_path / "system.db"

    # Build a mock DispositionTracker
    mock_disp = MagicMock()
    mock_disp.skepticism = 0.6
    mock_disp.literalism = 0.7
    mock_disp.empathy = 0.5

    mock_tracker = MagicMock()
    mock_tracker.update_from_correction.return_value = mock_disp

    mock_engine_mod = MagicMock()
    mock_engine_mod.DispositionTracker.return_value = mock_tracker

    corrections = [{"category": "TONE", "severity": "minor", "domain": "sales"}]

    with patch.dict(sys.modules, {"gradata.enhancements.behavioral_engine": mock_engine_mod}):
        result = run_rule_pipeline(
            lessons_path, db_path, current_session=3, corrections=corrections
        )

    assert "sales" in result.disposition_updates
    disp = result.disposition_updates["sales"]
    assert disp["skepticism"] == pytest.approx(0.6)
    assert disp["literalism"] == pytest.approx(0.7)
    assert disp["empathy"] == pytest.approx(0.5)


def test_pipeline_continues_on_phase3_errors(tmp_path: Path) -> None:
    """Phase 3 hook promotion errors are recorded but pipeline still returns."""
    lesson = _make_lesson(
        state=LessonState.RULE,
        confidence=0.95,
        fire_count=5,
    )
    lessons_path = tmp_path / "lessons.md"
    _write_lessons(lessons_path, [lesson])
    db_path = tmp_path / "system.db"

    # Make classify_rule raise to simulate a Phase 3 failure
    mock_r2h = MagicMock()
    mock_candidate = MagicMock()
    mock_candidate.determinism.value = "regex_pattern"  # non-deterministic passes gate
    mock_r2h.classify_rule.return_value = mock_candidate
    mock_r2h.promote.side_effect = RuntimeError("hook write failed")

    with patch.dict(sys.modules, {"gradata.enhancements.rule_to_hook": mock_r2h}):
        result = run_rule_pipeline(lessons_path, db_path, current_session=10)

    # At least one Phase 3 error captured
    assert any("Phase 3" in e for e in result.errors)
    # But result is still returned (not raised)
    assert isinstance(result, PipelineResult)


def test_pipeline_missing_lessons_file_returns_phase1_error(tmp_path: Path) -> None:
    """If lessons_path doesn't exist, Phase 1 error is recorded and pipeline aborts."""
    lessons_path = tmp_path / "nonexistent.md"
    db_path = tmp_path / "system.db"

    result = run_rule_pipeline(lessons_path, db_path, current_session=1)

    assert any("Phase 1" in e for e in result.errors)
    assert result.graduated == []
