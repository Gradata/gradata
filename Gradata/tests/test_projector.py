"""
Tests for gradata._projector — Memory-tool file projection.
"""

from __future__ import annotations

from datetime import date as _date
from pathlib import Path

import pytest

from gradata import Brain
from gradata._projector import (
    ProjectionResult,
    project,
    _classify,
    _ALL_FILES,
    _VOICE,
    _DECISIONS,
    _PROCESS,
    _PREFERENCES,
    _RELATIONS,
)
from gradata._types import Lesson, LessonState


def _mk(category: str, description: str, state: LessonState = LessonState.RULE,
        confidence: float = 0.95) -> Lesson:
    """Tiny factory for Lesson objects with the minimum required fields."""
    return Lesson(
        date=_date(2026, 4, 30).isoformat(),
        state=state,
        confidence=confidence,
        category=category,
        description=description,
    )


# ─── Classifier ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "category,expected",
    [
        ("DRAFTING", _VOICE),
        ("FORMAT", _VOICE),
        ("EMAIL", _VOICE),
        ("ACCURACY", _DECISIONS),
        ("ARCHITECTURE", _DECISIONS),
        ("PROCESS", _PROCESS),
        ("WORKFLOW", _PROCESS),
        ("PREFERENCE", _PREFERENCES),
        ("TOOL", _PREFERENCES),
        ("RELATION", _RELATIONS),
        ("PERSON", _RELATIONS),
        ("UNKNOWN_CAT", _DECISIONS),  # safest fallback
        ("", _DECISIONS),
        ("drafting", _VOICE),  # case-insensitive
    ],
)
def test_classifier_routes_each_category(category: str, expected: str):
    """Activation-entropy classifier must route every category to its bucket
    deterministically, with case-insensitivity and an unknown-category
    fallback that lands somewhere safe."""
    lesson = _mk(category, "x")
    assert _classify(lesson) == expected


# ─── End-to-end projection ───────────────────────────────────────────────────


def test_project_creates_all_files(fresh_brain: Brain, monkeypatch):
    """Even with zero lessons, the projector creates all five canonical files
    so the Memory tool sees consistent paths and doesn't 404 on absent buckets."""

    monkeypatch.setattr(fresh_brain, "_load_lessons", lambda: [])
    result = project(fresh_brain)

    assert isinstance(result, ProjectionResult)
    assert result.memories_dir == fresh_brain.dir / "memories"
    assert result.memories_dir.is_dir()

    for name in _ALL_FILES:
        assert (result.memories_dir / name).exists(), f"{name} not written"

    assert result.rules_total == 0
    assert sum(result.rules_by_file.values()) == 0


def test_project_routes_lessons_to_correct_files(fresh_brain: Brain, monkeypatch):
    """A representative mix of lessons must land in the right buckets and
    nothing else. Counts are how we verify routing without parsing markdown."""

    lessons = [
        _mk("DRAFTING", "use short subject lines"),
        _mk("EMAIL", "always cc oliver"),
        _mk("ACCURACY", "verify pricing before quoting"),
        _mk("ARCHITECTURE", "prefer SQLite for source-of-truth"),
        _mk("PROCESS", "PRs through review only"),
        _mk("PREFERENCE", "Polestar over Poetry"),
        _mk("RELATION", "Bob (acme) prefers formal tone"),
    ]
    monkeypatch.setattr(fresh_brain, "_load_lessons", lambda: lessons)

    result = project(fresh_brain)

    assert result.rules_total == 7
    assert result.rules_by_file[_VOICE] == 2
    assert result.rules_by_file[_DECISIONS] == 2
    assert result.rules_by_file[_PROCESS] == 1
    assert result.rules_by_file[_PREFERENCES] == 1
    assert result.rules_by_file[_RELATIONS] == 1

    voice_text = (result.memories_dir / _VOICE).read_text()
    assert "short subject lines" in voice_text
    assert "always cc oliver" in voice_text
    # Voice content must NOT include decision rules — that would defeat
    # the activation-entropy split.
    assert "verify pricing" not in voice_text


def test_project_filters_by_state(fresh_brain: Brain, monkeypatch):
    """INSTINCT lessons must NOT be projected — they haven't graduated.
    Projecting unstable rules would poison the cache prefix."""

    lessons = [
        _mk("DRAFTING", "stable voice rule", state=LessonState.RULE),
        _mk("DRAFTING", "unstable instinct", state=LessonState.INSTINCT),
        _mk("DRAFTING", "pattern tier ok", state=LessonState.PATTERN),
        _mk("DRAFTING", "killed", state=LessonState.KILLED),
    ]
    monkeypatch.setattr(fresh_brain, "_load_lessons", lambda: lessons)

    result = project(fresh_brain)

    voice_text = (result.memories_dir / _VOICE).read_text()
    assert "stable voice rule" in voice_text
    assert "pattern tier ok" in voice_text
    assert "unstable instinct" not in voice_text
    assert "killed" not in voice_text
    assert result.rules_total == 2


def test_project_is_deterministic(fresh_brain: Brain, monkeypatch):
    """Same input → byte-identical output. Critical for prompt caching:
    if the projector flips file order or rule order between runs, every
    cache write tax (1.25-2x) gets paid for nothing."""

    lessons = [
        _mk("DRAFTING", "rule A", confidence=0.95),
        _mk("DRAFTING", "rule B", confidence=0.95),
        _mk("DRAFTING", "rule C", confidence=0.92),
    ]
    monkeypatch.setattr(fresh_brain, "_load_lessons", lambda: lessons)

    r1 = project(fresh_brain)
    r2 = project(fresh_brain)

    assert r1.digest == r2.digest
    # Second pass is all unchanged → mtimes preserved → caches stay hot
    assert r2.files_written == ()
    assert set(r2.files_unchanged) == set(_ALL_FILES)


def test_project_skips_unchanged_files(fresh_brain: Brain, monkeypatch):
    """When only one bucket changes, only that file gets rewritten."""
    lessons_v1 = [_mk("DRAFTING", "voice rule")]
    monkeypatch.setattr(fresh_brain, "_load_lessons", lambda: lessons_v1)
    project(fresh_brain)

    # Add a decisions rule; voice file must remain untouched.
    lessons_v2 = lessons_v1 + [_mk("ACCURACY", "decision rule")]
    monkeypatch.setattr(fresh_brain, "_load_lessons", lambda: lessons_v2)
    r2 = project(fresh_brain)

    assert _DECISIONS in r2.files_written
    assert _VOICE in r2.files_unchanged


def test_project_dry_run_writes_nothing(fresh_brain: Brain, monkeypatch, tmp_path: Path):
    """dry_run renders in memory but leaves disk untouched. Useful for the
    rentable-brain SKU's preview-before-commit flow."""
    lessons = [_mk("DRAFTING", "voice rule")]
    monkeypatch.setattr(fresh_brain, "_load_lessons", lambda: lessons)

    out = tmp_path / "preview"
    result = project(fresh_brain, output_dir=out, dry_run=True)

    # Directory exists (mkdir is fine) but files do not.
    assert out.is_dir()
    assert not (out / _VOICE).exists()
    # Result still reports what *would* have been written.
    assert _VOICE in result.files_written


def test_project_custom_output_dir(fresh_brain: Brain, monkeypatch, tmp_path: Path):
    """Custom output_dir enables `/personas/<id>/memories/` per-persona namespacing
    that the rentable-brain SKU needs for path-based isolation."""
    persona_dir = tmp_path / "personas" / "founder-x" / "memories"
    monkeypatch.setattr(fresh_brain, "_load_lessons",
                        lambda: [_mk("DRAFTING", "founder voice")])

    result = project(fresh_brain, output_dir=persona_dir)

    assert result.memories_dir == persona_dir
    assert (persona_dir / _VOICE).read_text().count("founder voice") == 1


def test_project_sort_is_confidence_desc(fresh_brain: Brain, monkeypatch):
    """Higher-confidence rules render first. Memory tool truncation that
    drops the tail must drop the lowest-confidence rules, never the highest."""
    lessons = [
        _mk("DRAFTING", "low conf", confidence=0.60),
        _mk("DRAFTING", "high conf", confidence=0.99),
        _mk("DRAFTING", "mid conf", confidence=0.80),
    ]
    monkeypatch.setattr(fresh_brain, "_load_lessons", lambda: lessons)
    project(fresh_brain)

    text = (fresh_brain.dir / "memories" / _VOICE).read_text()
    pos_high = text.find("high conf")
    pos_mid = text.find("mid conf")
    pos_low = text.find("low conf")
    assert 0 < pos_high < pos_mid < pos_low


def test_project_atomic_write_no_torn_reads(fresh_brain: Brain, monkeypatch):
    """The .tmp + replace pattern means a Memory tool reading concurrently
    sees either the old file or the new file, never a half-written one.
    We can't simulate true concurrency cheaply, but we can assert no .tmp
    file leaks after a normal run."""
    monkeypatch.setattr(fresh_brain, "_load_lessons",
                        lambda: [_mk("DRAFTING", "voice rule")])
    project(fresh_brain)

    leaked = list((fresh_brain.dir / "memories").glob("*.tmp"))
    assert leaked == [], f"leaked tmp files: {leaked}"
