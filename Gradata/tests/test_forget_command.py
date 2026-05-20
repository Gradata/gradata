"""Tests for `gradata forget` — soft-delete lessons by selector."""

from __future__ import annotations

import contextlib
from types import SimpleNamespace

import pytest

try:
    from gradata.cli import cmd_forget
except ImportError:
    pytest.skip("gradata SDK not importable", allow_module_level=True)


@pytest.fixture
def seeded_brain(tmp_path):
    """Return a Brain with 3 active lessons across 2 categories."""
    from gradata import Brain

    brain_dir = tmp_path / "brain"
    brain = Brain.init(str(brain_dir), domain="Test")

    # Seed via the public correct() API so the events table matches reality.
    # Each correction generates a lesson via the auto-graduation pipeline;
    # we explicitly select category to ensure both buckets exist.
    brain.correct(
        draft="Dear Sir or Madam",
        final="Hey there",
        category="TONE",
    )
    brain.correct(
        draft="The following is a list:",
        final="Here:",
        category="TONE",
    )
    brain.correct(
        draft="def foo():",
        final="def foo() -> None:",
        category="STYLE",
    )
    return brain, brain_dir


def _run_forget(brain_dir, what, yes=True, capsys=None):
    """Invoke cmd_forget and return captured stdout."""
    args = SimpleNamespace(brain_dir=str(brain_dir), what=what, yes=yes)
    with contextlib.suppress(SystemExit):
        cmd_forget(args)
    return capsys.readouterr().out if capsys else ""


def test_forget_last_drops_one_lesson(seeded_brain, capsys):
    brain, brain_dir = seeded_brain
    before = len([l for l in _active_lessons(brain)])
    out = _run_forget(brain_dir, "last", yes=True, capsys=capsys)
    after = len([l for l in _active_lessons(brain)])
    assert "Will forget 1 lesson" in out
    assert "Forgotten: 1 lesson" in out
    assert after == before - 1


def test_forget_last_n_drops_n_lessons(seeded_brain, capsys):
    brain, brain_dir = seeded_brain
    before = len([l for l in _active_lessons(brain)])
    out = _run_forget(brain_dir, "last 2", yes=True, capsys=capsys)
    after = len([l for l in _active_lessons(brain)])
    assert "Will forget 2 lessons" in out
    assert after == before - 2


def test_forget_all_category_drops_matching(seeded_brain, capsys):
    brain, brain_dir = seeded_brain
    tone_before = len([l for l in _active_lessons(brain) if l.category.upper() == "TONE"])
    assert tone_before >= 1
    out = _run_forget(brain_dir, "all TONE", yes=True, capsys=capsys)
    tone_after = len([l for l in _active_lessons(brain) if l.category.upper() == "TONE"])
    assert tone_after == 0
    assert "Will forget" in out


def test_forget_fuzzy_description(seeded_brain, capsys):
    brain, brain_dir = seeded_brain
    # Find an actual lesson description substring to match on
    active = _active_lessons(brain)
    assert active, "test prerequisite: at least one lesson seeded"
    # Take the first word of the first lesson's description as the fuzzy key.
    # This is robust to whatever the auto-graduation pipeline produced.
    descs = [(l.description or "") for l in active]
    candidate = next((d for d in descs if len(d) > 3), "")
    assert candidate, f"no usable descriptions found: {descs}"
    needle = candidate.split()[0]
    out = _run_forget(brain_dir, needle, yes=True, capsys=capsys)
    assert "Will forget" in out


def test_forget_no_matches_returns_clean_error(seeded_brain, capsys):
    brain, brain_dir = seeded_brain
    out = _run_forget(brain_dir, "nonexistent-phrase-zzz", yes=True, capsys=capsys)
    assert "No active lessons match" in out or "No matches" in out


def test_forget_unknown_category_says_no_matches(seeded_brain, capsys):
    brain, brain_dir = seeded_brain
    out = _run_forget(brain_dir, "all NONEXISTENT", yes=True, capsys=capsys)
    assert "No matches" in out or "No active lessons in" in out


# ---- helpers --------------------------------------------------------------


def _active_lessons(brain):
    from gradata._types import LessonState
    from gradata.enhancements.self_improvement import parse_lessons

    p = brain._find_lessons_path()
    if not p or not p.is_file():
        return []
    return [
        l
        for l in parse_lessons(p.read_text(encoding="utf-8"))
        if l.state in (LessonState.INSTINCT, LessonState.PATTERN, LessonState.RULE)
    ]
