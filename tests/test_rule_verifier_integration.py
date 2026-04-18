"""Integration tests: rule_verifier wired into run_rule_pipeline.

Covers:
- GRADATA_RULE_VERIFIER=1 → verifications persisted, get_verification_stats()
  returns non-zero counts.
- No env var set → rule_verifications table stays empty, no regression.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from gradata._types import Lesson, LessonState
from gradata.enhancements.rule_pipeline import run_rule_pipeline
from gradata.enhancements.rule_pipeline import ensure_table, get_verification_stats
from gradata.enhancements.self_improvement import format_lessons


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_lesson(
    category: str = "DRAFTING",
    description: str = "Never use em dashes",
    state: LessonState = LessonState.RULE,
    confidence: float = 0.92,
) -> Lesson:
    return Lesson(
        date="2026-01-01",
        state=state,
        confidence=confidence,
        category=category,
        description=description,
        fire_count=3,
        sessions_since_fire=0,
    )


def _setup_brain(tmp_path: Path, lessons: list[Lesson]) -> tuple[Path, Path]:
    """Write lessons.md and touch system.db; return (lessons_path, db_path)."""
    lessons_path = tmp_path / "lessons.md"
    lessons_path.write_text(format_lessons(lessons), encoding="utf-8")
    db_path = tmp_path / "system.db"
    # Create a minimal SQLite DB so db_path.is_file() == True
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS events "
            "(id INTEGER PRIMARY KEY, type TEXT, session INTEGER, data TEXT)"
        )
    return lessons_path, db_path


# ---------------------------------------------------------------------------
# Tests: env flag ON
# ---------------------------------------------------------------------------


class TestRuleVerifierIntegration:
    """Pipeline runs WITH GRADATA_RULE_VERIFIER=1 → verifications persisted."""

    def test_verifications_persisted_when_flag_on(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GRADATA_RULE_VERIFIER", "1")

        lessons = [_make_lesson(description="Never use em dashes")]
        lessons_path, db_path = _setup_brain(tmp_path, lessons)

        # A correction whose draft contains an em dash — should trigger a violation
        corrections = [
            {
                "draft": "This output has an em dash \u2014 right here.",
                "final": "This output has a dash right here.",
                "category": "DRAFTING",
                "severity": "minor",
            }
        ]

        run_rule_pipeline(
            lessons_path=lessons_path,
            db_path=db_path,
            current_session=1,
            corrections=corrections,
        )

        stats = get_verification_stats(db_path)
        assert stats["total_checks"] >= 1, "Expected at least one verification row to be written"
        assert stats["passed"] < stats["total_checks"], (
            "Expected at least one violation (em dash in draft)"
        )

    def test_stats_non_zero_after_pipeline(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GRADATA_RULE_VERIFIER", "1")

        lessons = [
            _make_lesson(description="Never use em dashes"),
            _make_lesson(category="PRICING", description="Do not include dollar amounts"),
        ]
        lessons_path, db_path = _setup_brain(tmp_path, lessons)

        corrections = [
            {
                "draft": "Plan costs $50 per month \u2014 see below.",
                "final": "Plan pricing available on request.",
                "category": "PRICING",
                "severity": "moderate",
            }
        ]

        run_rule_pipeline(
            lessons_path=lessons_path,
            db_path=db_path,
            current_session=2,
            corrections=corrections,
        )

        stats = get_verification_stats(db_path)
        assert stats["total_checks"] > 0
        assert "pass_rate" in stats

    def test_clean_draft_all_pass(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GRADATA_RULE_VERIFIER", "1")

        lessons = [_make_lesson(description="Never use em dashes")]
        lessons_path, db_path = _setup_brain(tmp_path, lessons)

        # Draft has no em dashes
        corrections = [
            {
                "draft": "A clean sentence with no dashes at all.",
                "final": "A clean sentence.",
                "category": "DRAFTING",
                "severity": "trivial",
            }
        ]

        run_rule_pipeline(
            lessons_path=lessons_path,
            db_path=db_path,
            current_session=3,
            corrections=corrections,
        )

        stats = get_verification_stats(db_path)
        assert stats["total_checks"] >= 1
        assert stats["pass_rate"] == 1.0

    def test_corrections_without_draft_skipped(self, tmp_path, monkeypatch):
        """Corrections missing 'draft' key must not cause errors."""
        monkeypatch.setenv("GRADATA_RULE_VERIFIER", "1")

        lessons = [_make_lesson(description="Never use em dashes")]
        lessons_path, db_path = _setup_brain(tmp_path, lessons)

        corrections = [{"final": "some text", "category": "DRAFTING", "severity": "minor"}]

        result = run_rule_pipeline(
            lessons_path=lessons_path,
            db_path=db_path,
            current_session=4,
            corrections=corrections,
        )

        # No crash and no verification errors
        pipeline_errors = [e for e in result.errors if "rule verification" in e]
        assert pipeline_errors == []

        # Table stays empty since draft was absent
        ensure_table(db_path)
        stats = get_verification_stats(db_path)
        assert stats["total_checks"] == 0


# ---------------------------------------------------------------------------
# Tests: env flag OFF (zero regression)
# ---------------------------------------------------------------------------


class TestRuleVerifierFlagOff:
    """Pipeline runs WITHOUT env var → table stays empty."""

    def test_table_empty_when_flag_off(self, tmp_path, monkeypatch):
        monkeypatch.delenv("GRADATA_RULE_VERIFIER", raising=False)

        lessons = [_make_lesson(description="Never use em dashes")]
        lessons_path, db_path = _setup_brain(tmp_path, lessons)

        corrections = [
            {
                "draft": "This has an em dash \u2014 here.",
                "final": "This has a dash here.",
                "category": "DRAFTING",
                "severity": "minor",
            }
        ]

        run_rule_pipeline(
            lessons_path=lessons_path,
            db_path=db_path,
            current_session=10,
            corrections=corrections,
        )

        # rule_verifications table should not even exist unless we created it
        with sqlite3.connect(str(db_path)) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        assert "rule_verifications" not in tables, (
            "rule_verifications table must not be created when flag is off"
        )

    def test_no_regression_pipeline_result(self, tmp_path, monkeypatch):
        """Existing pipeline result fields must be unaffected when flag is off."""
        monkeypatch.delenv("GRADATA_RULE_VERIFIER", raising=False)

        lessons = [_make_lesson(description="Never use em dashes")]
        lessons_path, db_path = _setup_brain(tmp_path, lessons)

        result = run_rule_pipeline(
            lessons_path=lessons_path,
            db_path=db_path,
            current_session=11,
            corrections=[],
        )

        # PipelineResult must still be a valid object
        assert hasattr(result, "graduated")
        assert hasattr(result, "errors")
        # No rule verification errors when flag is off
        rule_verif_errors = [e for e in result.errors if "rule verification" in e]
        assert rule_verif_errors == []
