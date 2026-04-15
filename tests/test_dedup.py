"""Tests for observation dedup (gradata.enhancements.dedup).

Covers:
- Fingerprint stability and normalization
- Category-awareness (same text, different category => different fp)
- is_duplicate / register_observation round-trip
- Window boundary behavior
- check_and_register convenience
- End-to-end: brain.correct() does NOT inflate fire_count / lesson count
  when the same correction is submitted repeatedly in-window.
"""
from __future__ import annotations

import pytest

from gradata.enhancements.dedup import (
    check_and_register,
    is_duplicate,
    observation_fingerprint,
    register_observation,
)

# ---------------------------------------------------------------------------
# Fingerprint
# ---------------------------------------------------------------------------

def test_fingerprint_is_stable():
    fp1 = observation_fingerprint("Don't use em-dashes.", category="FORMAT")
    fp2 = observation_fingerprint("Don't use em-dashes.", category="FORMAT")
    assert fp1 == fp2
    assert len(fp1) == 40  # sha1 hex


def test_fingerprint_normalizes_case_whitespace_punct():
    # case + trailing punct + extra whitespace all normalize together
    fp1 = observation_fingerprint("Don't use em-dashes.", category="FORMAT")
    fp2 = observation_fingerprint("  DON'T  USE  EM-DASHES!!  ", category="format")
    fp3 = observation_fingerprint("don't use em-dashes", category="Format")
    assert fp1 == fp2 == fp3


def test_fingerprint_category_aware():
    # Same text in different categories is NOT the same observation
    fp_format = observation_fingerprint("be more specific", category="FORMAT")
    fp_tone = observation_fingerprint("be more specific", category="TONE")
    assert fp_format != fp_tone


def test_fingerprint_text_differences_break_match():
    # Genuinely different corrections must fingerprint differently
    fp1 = observation_fingerprint("Don't use em-dashes.", category="FORMAT")
    fp2 = observation_fingerprint("Always use bullet lists.", category="FORMAT")
    assert fp1 != fp2


# ---------------------------------------------------------------------------
# Register / is_duplicate
# ---------------------------------------------------------------------------

def test_first_sighting_is_not_duplicate(tmp_path):
    db = tmp_path / "dedup.db"
    fp = observation_fingerprint("skip em dashes", category="FORMAT")
    assert is_duplicate(db, fp, current_session=1) is False
    result = register_observation(db, fp, category="FORMAT", session=1)
    assert result["new"] is True
    assert result["seen_count"] == 1


def test_second_sighting_same_session_is_duplicate(tmp_path):
    db = tmp_path / "dedup.db"
    fp = observation_fingerprint("skip em dashes", category="FORMAT")
    register_observation(db, fp, category="FORMAT", session=5)
    # Second time: already in DB, same session => within window
    assert is_duplicate(db, fp, current_session=5, recent_window_sessions=10) is True
    result = register_observation(db, fp, category="FORMAT", session=5)
    assert result["new"] is False
    assert result["seen_count"] == 2


def test_window_boundary_outside_window_is_not_duplicate(tmp_path):
    db = tmp_path / "dedup.db"
    fp = observation_fingerprint("skip em dashes", category="FORMAT")
    # Register at session 1
    register_observation(db, fp, category="FORMAT", session=1)
    # Current session 20, window 10 => oldest-in-window is session 11.
    # Last sighting at session 1 is OUTSIDE the window.
    assert is_duplicate(db, fp, current_session=20, recent_window_sessions=10) is False


def test_window_boundary_inside_window_is_duplicate(tmp_path):
    db = tmp_path / "dedup.db"
    fp = observation_fingerprint("skip em dashes", category="FORMAT")
    register_observation(db, fp, category="FORMAT", session=12)
    # Current session 20, window 10 => oldest-in-window session 11.
    # Last sighting at session 12 is INSIDE the window.
    assert is_duplicate(db, fp, current_session=20, recent_window_sessions=10) is True


def test_window_exact_edge_is_duplicate(tmp_path):
    db = tmp_path / "dedup.db"
    fp = observation_fingerprint("skip em dashes", category="FORMAT")
    register_observation(db, fp, category="FORMAT", session=11)
    # current=20, window=10 => oldest-in-window is 11. sighting at 11 => inside
    assert is_duplicate(db, fp, current_session=20, recent_window_sessions=10) is True


def test_different_text_is_not_duplicate(tmp_path):
    db = tmp_path / "dedup.db"
    fp1 = observation_fingerprint("skip em dashes", category="FORMAT")
    fp2 = observation_fingerprint("use bullet lists", category="FORMAT")
    register_observation(db, fp1, category="FORMAT", session=1)
    assert is_duplicate(db, fp2, current_session=1) is False


def test_register_persists_seen_count(tmp_path):
    db = tmp_path / "dedup.db"
    fp = observation_fingerprint("skip em dashes", category="FORMAT")
    for i in range(5):
        register_observation(db, fp, category="FORMAT", session=i + 1)
    # One logical observation, five sightings
    import sqlite3
    with sqlite3.connect(str(db)) as conn:
        rows = list(
            conn.execute("SELECT fingerprint, seen_count FROM observation_dedup")
        )
    assert len(rows) == 1
    assert rows[0][0] == fp
    assert rows[0][1] == 5


def test_check_and_register_roundtrip(tmp_path):
    db = tmp_path / "dedup.db"
    first = check_and_register(
        db, "Don't use em-dashes.", category="FORMAT", session=1,
        recent_window_sessions=10,
    )
    assert first["is_duplicate"] is False
    assert first["new"] is True
    assert first["seen_count"] == 1

    second = check_and_register(
        db, "  DON'T  USE  EM-DASHES!!  ", category="format", session=2,
        recent_window_sessions=10,
    )
    assert second["is_duplicate"] is True  # was already present before this register
    assert second["new"] is False
    assert second["seen_count"] == 2
    assert second["fingerprint"] == first["fingerprint"]


# ---------------------------------------------------------------------------
# End-to-end via Brain.correct — the real-world harm we're preventing
# ---------------------------------------------------------------------------

def test_brain_correct_suppresses_duplicate_lesson_reinforcement(fresh_brain):
    """Same correction applied 10 times must not inflate fire_count 10x."""
    brain = fresh_brain

    draft = "We can definitely maybe perhaps hit those KPIs — probably."
    final = "We will hit those KPIs."

    # First correction: creates a new lesson
    result = brain.correct(draft, final, category="DRAFTING", session=1)
    assert result.get("observation_deduped") is not True

    # Nine more identical corrections, same session => all should dedup
    dedup_hits = 0
    for _ in range(9):
        r = brain.correct(draft, final, category="DRAFTING", session=1)
        if r.get("observation_deduped"):
            dedup_hits += 1

    assert dedup_hits == 9, (
        f"Expected 9 dedup hits, got {dedup_hits}. "
        "Dedup must suppress in-window duplicates."
    )

    # Lesson fire_count must NOT have been inflated by 10
    final_lessons = brain._load_lessons() if hasattr(brain, "_load_lessons") else []
    drafting_lessons = [l for l in final_lessons if l.category == "DRAFTING"]
    assert len(drafting_lessons) >= 1
    # fire_count should reflect the single non-dedup correction, not 10
    for l in drafting_lessons:
        assert l.fire_count <= 2, (
            f"fire_count={l.fire_count} for lesson {l.description!r}. "
            "Dedup should have prevented inflation."
        )


def test_brain_correct_annotates_fingerprint_and_seen_count(fresh_brain):
    brain = fresh_brain
    result = brain.correct(
        "maybe we will maybe hit KPIs",
        "We will hit KPIs.",
        category="DRAFTING",
        session=1,
    )
    assert "observation_fingerprint" in result
    assert isinstance(result["observation_fingerprint"], str)
    assert len(result["observation_fingerprint"]) == 40
    assert result.get("observation_seen_count") == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
