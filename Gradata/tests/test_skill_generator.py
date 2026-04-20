"""
Tests for skill generator and skill enhancement agent.

Covers:
1. Rule below 0.90 confidence -> no skill generated
2. Rule with fire_count < 3 -> no skill generated
3. Valid rule generates SKILL.md with correct frontmatter
4. Generated skill passes review_generated_skill validation
5. Skill with placeholder text fails review
6. Skill with low confidence fails review
7. Missing directive section fails review
8. Pipeline generates skills when GRADATA_ENABLE_SKILL_EXPORT set
9. Pipeline rejects bad skills and cleans up file
10. Slug generation handles special characters

Run: pytest tests/test_skill_generator.py -xvs
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from gradata._types import Lesson, LessonState
from gradata.enhancements.rule_pipeline import (
    _generate_skill_file,
    review_generated_skill,
    run_rule_pipeline,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_lesson(
    state: LessonState = LessonState.RULE,
    confidence: float = 0.92,
    fire_count: int = 5,
    category: str = "DRAFTING",
    description: str = "Always write concise sentences in emails",
) -> Lesson:
    return Lesson(
        date="2026-01-01",
        state=state,
        confidence=confidence,
        category=category,
        description=description,
        fire_count=fire_count,
    )


def _write_skill(skill_path: Path, content: str) -> None:
    skill_path.parent.mkdir(parents=True, exist_ok=True)
    skill_path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Rule below 0.90 confidence -> no skill generated
# ---------------------------------------------------------------------------

class TestGenerateSkillFileQualityGate:

    def test_low_confidence_returns_none(self, tmp_path):
        lesson = _make_lesson(confidence=0.85)
        result = _generate_skill_file(lesson, tmp_path)
        assert result is None

    def test_exactly_at_threshold_passes(self, tmp_path):
        lesson = _make_lesson(confidence=0.90)
        result = _generate_skill_file(lesson, tmp_path)
        assert result is not None

    # ---------------------------------------------------------------------------
    # 2. Rule with fire_count < 3 -> no skill generated
    # ---------------------------------------------------------------------------

    def test_low_fire_count_returns_none(self, tmp_path):
        lesson = _make_lesson(fire_count=2)
        result = _generate_skill_file(lesson, tmp_path)
        assert result is None

    def test_fire_count_exactly_3_passes(self, tmp_path):
        lesson = _make_lesson(fire_count=3)
        result = _generate_skill_file(lesson, tmp_path)
        assert result is not None

    def test_non_rule_state_returns_none(self, tmp_path):
        lesson = _make_lesson(state=LessonState.PATTERN, confidence=0.95, fire_count=10)
        result = _generate_skill_file(lesson, tmp_path)
        assert result is None

    def test_instinct_state_returns_none(self, tmp_path):
        lesson = _make_lesson(state=LessonState.INSTINCT, confidence=0.95, fire_count=10)
        result = _generate_skill_file(lesson, tmp_path)
        assert result is None


# ---------------------------------------------------------------------------
# 3. Valid rule generates SKILL.md with correct frontmatter
# ---------------------------------------------------------------------------

class TestGenerateSkillFileOutput:

    def test_creates_skill_md_file(self, tmp_path):
        lesson = _make_lesson()
        result = _generate_skill_file(lesson, tmp_path)
        assert result is not None
        assert result.name == "SKILL.md"
        assert result.exists()

    def test_frontmatter_starts_with_triple_dash(self, tmp_path):
        lesson = _make_lesson()
        skill_path = _generate_skill_file(lesson, tmp_path)
        text = skill_path.read_text(encoding="utf-8")
        assert text.startswith("---")

    def test_frontmatter_contains_confidence(self, tmp_path):
        lesson = _make_lesson(confidence=0.93)
        skill_path = _generate_skill_file(lesson, tmp_path)
        text = skill_path.read_text(encoding="utf-8")
        assert "confidence: 0.93" in text

    def test_frontmatter_contains_category(self, tmp_path):
        lesson = _make_lesson(category="ACCURACY")
        skill_path = _generate_skill_file(lesson, tmp_path)
        text = skill_path.read_text(encoding="utf-8")
        assert "category: ACCURACY" in text

    def test_frontmatter_contains_source(self, tmp_path):
        lesson = _make_lesson()
        skill_path = _generate_skill_file(lesson, tmp_path)
        text = skill_path.read_text(encoding="utf-8")
        assert "source: gradata-behavioral-engine" in text

    def test_directive_section_present(self, tmp_path):
        lesson = _make_lesson()
        skill_path = _generate_skill_file(lesson, tmp_path)
        text = skill_path.read_text(encoding="utf-8")
        assert "## Directive" in text

    def test_directive_contains_description(self, tmp_path):
        desc = "Always write concise sentences in emails"
        lesson = _make_lesson(description=desc)
        skill_path = _generate_skill_file(lesson, tmp_path)
        text = skill_path.read_text(encoding="utf-8")
        assert desc in text

    def test_file_placed_in_slug_subdir(self, tmp_path):
        lesson = _make_lesson(category="DRAFTING", description="Use short sentences always")
        skill_path = _generate_skill_file(lesson, tmp_path)
        # Parent dir should be the slug subdir, not the output_dir root
        assert skill_path.parent != tmp_path
        assert skill_path.parent.parent == tmp_path

    # ---------------------------------------------------------------------------
    # 10. Slug generation handles special characters
    # ---------------------------------------------------------------------------

    def test_slug_strips_special_chars(self, tmp_path):
        lesson = _make_lesson(
            category="DATA_INTEGRITY",
            description="Never use em-dashes -- in prose!!! OK?",
        )
        skill_path = _generate_skill_file(lesson, tmp_path)
        slug = skill_path.parent.name
        # slug should only contain lowercase alphanumerics and hyphens
        assert all(c.isalnum() or c == "-" for c in slug)
        assert not slug.startswith("-")
        assert not slug.endswith("-")

    def test_slug_lowercased(self, tmp_path):
        lesson = _make_lesson(category="PROCESS", description="Run Tests After Code Changes")
        skill_path = _generate_skill_file(lesson, tmp_path)
        slug = skill_path.parent.name
        assert slug == slug.lower()


# ---------------------------------------------------------------------------
# 4. Generated skill passes review_generated_skill validation
# ---------------------------------------------------------------------------

class TestReviewGeneratedSkillValid:

    def test_generated_skill_passes_review(self, tmp_path):
        lesson = _make_lesson()
        skill_path = _generate_skill_file(lesson, tmp_path)
        review = review_generated_skill(skill_path)
        assert review["valid"] is True
        assert review["issues"] == []

    def test_review_returns_path(self, tmp_path):
        lesson = _make_lesson()
        skill_path = _generate_skill_file(lesson, tmp_path)
        review = review_generated_skill(skill_path)
        assert review["path"] == str(skill_path)

    def test_review_returns_suggestions_list(self, tmp_path):
        lesson = _make_lesson()
        skill_path = _generate_skill_file(lesson, tmp_path)
        review = review_generated_skill(skill_path)
        assert isinstance(review["suggestions"], list)

    def test_auto_generated_description_triggers_suggestion(self, tmp_path):
        lesson = _make_lesson()
        skill_path = _generate_skill_file(lesson, tmp_path)
        review = review_generated_skill(skill_path)
        # The auto-generated description starts with "Auto-graduated"
        assert any("generic" in s for s in review["suggestions"])


# ---------------------------------------------------------------------------
# 5. Skill with placeholder text fails review
# ---------------------------------------------------------------------------

class TestReviewPlaceholder:

    def test_todo_in_content_fails(self, tmp_path):
        skill_path = tmp_path / "SKILL.md"
        _write_skill(skill_path, "---\nconfidence: 0.92\ndescription: A real description here\n---\n\n## Directive\n\nTODO: fill this in\n")
        review = review_generated_skill(skill_path)
        assert review["valid"] is False
        assert any("placeholder" in i.lower() for i in review["issues"])

    def test_requires_in_content_fails(self, tmp_path):
        skill_path = tmp_path / "SKILL.md"
        _write_skill(skill_path, "---\nconfidence: 0.92\ndescription: A real description here\n---\n\n## Directive\n\n(requires human review)\n")
        review = review_generated_skill(skill_path)
        assert review["valid"] is False
        assert any("placeholder" in i.lower() for i in review["issues"])


# ---------------------------------------------------------------------------
# 6. Skill with low confidence fails review
# ---------------------------------------------------------------------------

class TestReviewLowConfidence:

    def test_confidence_below_threshold_fails(self, tmp_path):
        skill_path = tmp_path / "SKILL.md"
        content = (
            "---\n"
            "confidence: 0.75\n"
            "description: A decent description for testing purposes\n"
            "---\n\n"
            "## Directive\n\n"
            "Do the thing correctly every time.\n"
        )
        _write_skill(skill_path, content)
        review = review_generated_skill(skill_path)
        assert review["valid"] is False
        assert any("confidence" in i.lower() for i in review["issues"])

    def test_confidence_exactly_09_passes(self, tmp_path):
        skill_path = tmp_path / "SKILL.md"
        content = (
            "---\n"
            "confidence: 0.90\n"
            "description: A decent description for testing purposes\n"
            "---\n\n"
            "## Directive\n\n"
            "Do the thing correctly every time.\n"
        )
        _write_skill(skill_path, content)
        review = review_generated_skill(skill_path)
        # 0.90 is exactly at threshold — should NOT flag as low confidence
        assert not any("confidence" in i.lower() for i in review["issues"])


# ---------------------------------------------------------------------------
# 7. Missing directive section fails review
# ---------------------------------------------------------------------------

class TestReviewMissingDirective:

    def test_missing_directive_section_fails(self, tmp_path):
        skill_path = tmp_path / "SKILL.md"
        content = (
            "---\n"
            "confidence: 0.92\n"
            "description: A decent description for testing purposes\n"
            "---\n\n"
            "## Context\n\n"
            "Some context info here.\n"
        )
        _write_skill(skill_path, content)
        review = review_generated_skill(skill_path)
        assert review["valid"] is False
        assert any("directive" in i.lower() for i in review["issues"])

    def test_empty_directive_section_fails(self, tmp_path):
        skill_path = tmp_path / "SKILL.md"
        content = (
            "---\n"
            "confidence: 0.92\n"
            "description: A decent description for testing purposes\n"
            "---\n\n"
            "## Directive\n\n"
            "## Context\n\n"
            "Some context.\n"
        )
        _write_skill(skill_path, content)
        review = review_generated_skill(skill_path)
        assert review["valid"] is False
        assert any("directive" in i.lower() for i in review["issues"])

    def test_missing_frontmatter_fails(self, tmp_path):
        skill_path = tmp_path / "SKILL.md"
        content = "# My Skill\n\n## Directive\n\nDo stuff.\n"
        _write_skill(skill_path, content)
        review = review_generated_skill(skill_path)
        assert review["valid"] is False
        assert any("frontmatter" in i.lower() for i in review["issues"])

    def test_too_short_fails(self, tmp_path):
        skill_path = tmp_path / "SKILL.md"
        _write_skill(skill_path, "---\n---\n")
        review = review_generated_skill(skill_path)
        assert review["valid"] is False
        assert any("short" in i.lower() for i in review["issues"])


# ---------------------------------------------------------------------------
# 8. Pipeline generates skills when GRADATA_ENABLE_SKILL_EXPORT set
# ---------------------------------------------------------------------------

class TestPipelineSkillExport:

    def _make_lessons_md(self, rule_desc: str = "Always validate input at boundaries") -> str:
        return (
            f"[2026-01-01] [RULE:0.92] PROCESS: {rule_desc}\n"
            "  Fire count: 5 | Sessions since fire: 2 | Misfires: 0\n"
            "\n"
        )

    def test_pipeline_generates_skill_with_env_var(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GRADATA_ENABLE_SKILL_EXPORT", "1")
        brain_dir = tmp_path / "brain"
        brain_dir.mkdir()
        lessons_path = brain_dir / "lessons.md"
        lessons_path.write_text(self._make_lessons_md(), encoding="utf-8")
        db_path = brain_dir / "system.db"

        result = run_rule_pipeline(lessons_path, db_path, current_session=10)

        assert len(result.skills_generated) >= 1
        assert all(Path(p).exists() for p in result.skills_generated)

    def test_pipeline_does_not_generate_skills_without_env_var(self, tmp_path, monkeypatch):
        monkeypatch.delenv("GRADATA_ENABLE_SKILL_EXPORT", raising=False)
        brain_dir = tmp_path / "brain"
        brain_dir.mkdir()
        lessons_path = brain_dir / "lessons.md"
        lessons_path.write_text(self._make_lessons_md(), encoding="utf-8")
        db_path = brain_dir / "system.db"

        result = run_rule_pipeline(lessons_path, db_path, current_session=10)

        assert result.skills_generated == []

    def test_pipeline_skips_low_confidence_lessons(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GRADATA_ENABLE_SKILL_EXPORT", "1")
        brain_dir = tmp_path / "brain"
        brain_dir.mkdir()
        # PATTERN state (below RULE) should not generate a skill
        lessons_path = brain_dir / "lessons.md"
        lessons_path.write_text(
            "[2026-01-01] [PATTERN:0.75] PROCESS: Always validate input at system boundaries\n"
            "  Fire count: 5 | Sessions since fire: 2 | Misfires: 0\n"
            "\n",
            encoding="utf-8",
        )
        db_path = brain_dir / "system.db"

        result = run_rule_pipeline(lessons_path, db_path, current_session=10)

        assert result.skills_generated == []

    # ---------------------------------------------------------------------------
    # 9. Pipeline rejects bad skills and cleans up file
    # ---------------------------------------------------------------------------

    def test_pipeline_rejects_skill_below_fire_count(self, tmp_path, monkeypatch):
        """A RULE-state lesson with fire_count < 3 should not generate a skill."""
        monkeypatch.setenv("GRADATA_ENABLE_SKILL_EXPORT", "1")
        brain_dir = tmp_path / "brain"
        brain_dir.mkdir()
        lessons_path = brain_dir / "lessons.md"
        lessons_path.write_text(
            "[2026-01-01] [RULE:0.92] PROCESS: Always validate input at system boundaries\n"
            "  Fire count: 2 | Sessions since fire: 1 | Misfires: 0\n"
            "\n",
            encoding="utf-8",
        )
        db_path = brain_dir / "system.db"

        result = run_rule_pipeline(lessons_path, db_path, current_session=5)

        # No valid skill should be generated
        assert result.skills_generated == []

    def test_pipeline_result_has_skills_generated_field(self, tmp_path, monkeypatch):
        """PipelineResult always has skills_generated list regardless of env var."""
        monkeypatch.delenv("GRADATA_ENABLE_SKILL_EXPORT", raising=False)
        brain_dir = tmp_path / "brain"
        brain_dir.mkdir()
        lessons_path = brain_dir / "lessons.md"
        lessons_path.write_text("", encoding="utf-8")
        db_path = brain_dir / "system.db"

        result = run_rule_pipeline(lessons_path, db_path, current_session=1)

        assert hasattr(result, "skills_generated")
        assert isinstance(result.skills_generated, list)
