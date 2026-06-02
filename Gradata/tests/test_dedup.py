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
        rows = list(conn.execute("SELECT fingerprint, seen_count FROM observation_dedup"))
    assert len(rows) == 1
    assert rows[0][0] == fp
    assert rows[0][1] == 5


def test_check_and_register_roundtrip(tmp_path):
    db = tmp_path / "dedup.db"
    first = check_and_register(
        db,
        "Don't use em-dashes.",
        category="FORMAT",
        session=1,
        recent_window_sessions=10,
    )
    assert first["is_duplicate"] is False
    assert first["new"] is True
    assert first["seen_count"] == 1

    second = check_and_register(
        db,
        "  DON'T  USE  EM-DASHES!!  ",
        category="format",
        session=2,
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
        f"Expected 9 dedup hits, got {dedup_hits}. Dedup must suppress in-window duplicates."
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


def test_brain_correct_semantic_near_duplicate_is_deduped(fresh_brain):
    brain = fresh_brain
    a1 = "We should probably maybe include the exact API endpoint in docs."
    b1 = "Include the exact API endpoint in docs."
    a2 = "We should maybe include the exact API endpoint in docs."
    b2 = "Please include the exact API endpoint in docs."

    first = brain.correct(a1, b1, category="DRAFTING", session=2)
    assert first.get("observation_deduped") is not True

    second = brain.correct(a2, b2, category="DRAFTING", session=2)
    assert second.get("observation_deduped") is True
    assert second.get("observation_dedup_reason") == "semantic"


def test_low_signal_floor_filters_tiny_non_meaningful_corrections(fresh_brain):
    brain = fresh_brain
    # Tiny punctuation-only edit; should be dropped by low-signal floor.
    draft = "This sentence has enough tokens that a single punctuation mark is low-signal"
    final = f"{draft}."
    result = brain.correct(draft, final, category="FORMAT", session=3)
    assert result.get("low_signal_filtered") is True
    assert result.get("lessons_created", 0) == 0


def test_dedup_does_not_inflate_lineage_correction_ids(fresh_brain):
    brain = fresh_brain
    draft = "we can maybe maybe probably ship this friday"
    final = "We can ship this Friday."

    brain.correct(draft, final, category="DRAFTING", session=4)
    for _ in range(5):
        brain.correct(draft, final, category="DRAFTING", session=4)

    lessons = [l for l in brain._load_lessons() if l.category == "DRAFTING"]
    assert lessons, "Expected at least one DRAFTING lesson"
    lineages = [len(l.correction_event_ids) for l in lessons]
    # Duplicate observations must not add new lineage IDs.
    assert max(lineages) == 1


# ── Cycle 3: category-aware noise filtering ──────────────────────────────────


def test_category_aware_floor_constants():
    """The FORMAT/DRAFTING floor (0.07) must be higher than the base floor (0.04)."""
    from gradata._core import (
        _FORMAT_DRAFTING_CATEGORIES,
        _FORMAT_DRAFTING_EDIT_DISTANCE_FLOOR,
        _LOW_SIGNAL_EDIT_DISTANCE_FLOOR,
    )

    assert _FORMAT_DRAFTING_EDIT_DISTANCE_FLOOR == 0.07
    assert _FORMAT_DRAFTING_EDIT_DISTANCE_FLOOR > _LOW_SIGNAL_EDIT_DISTANCE_FLOOR
    assert "FORMAT" in _FORMAT_DRAFTING_CATEGORIES
    assert "DRAFTING" in _FORMAT_DRAFTING_CATEGORIES
    assert "SECURITY" not in _FORMAT_DRAFTING_CATEGORIES
    assert "ACCURACY" not in _FORMAT_DRAFTING_CATEGORIES


def test_format_drafting_floor_filters_medium_ed_corrections(fresh_brain):
    """FORMAT/DRAFTING corrections with 0.04 ≤ ed < 0.07 are filtered as noise.

    Cycle-3 hypothesis: raise the low-signal floor to 0.07 for FORMAT/DRAFTING
    so synonym-swap edits that slip past the old 0.04 floor are blocked.
    We inject a controlled DiffResult (ed=0.05, severity='minor') so the test
    is deterministic regardless of diff-engine tuning.
    """
    from unittest.mock import patch

    from gradata.enhancements.diff_engine import DiffResult

    synthetic_diff = DiffResult(
        edit_distance=0.05,
        compression_distance=0.05,
        changed_sections=[],
        severity="minor",
        summary_stats={},
    )

    with patch("gradata.enhancements.diff_engine.compute_diff", return_value=synthetic_diff):
        result = fresh_brain.correct(
            "We should utilize the existing approach here.",
            "We should use the existing approach here.",
            category="DRAFTING",
            session=10,
        )

    assert result.get("low_signal_filtered") is True, (
        "Expected DRAFTING correction with ed=0.05 (< 0.07 floor) to be filtered as noise"
    )
    assert result.get("lessons_created", 0) == 0


def test_format_floor_does_not_filter_above_threshold(fresh_brain):
    """FORMAT/DRAFTING corrections with ed ≥ 0.07 must NOT be filtered."""
    from unittest.mock import patch

    from gradata.enhancements.diff_engine import DiffResult

    synthetic_diff = DiffResult(
        edit_distance=0.08,
        compression_distance=0.08,
        changed_sections=[],
        severity="minor",
        summary_stats={},
    )

    with patch("gradata.enhancements.diff_engine.compute_diff", return_value=synthetic_diff):
        result = fresh_brain.correct(
            "We should utilize this approach.",
            "We should use this approach.",
            category="FORMAT",
            session=12,
        )

    assert result.get("low_signal_filtered") is not True, (
        "FORMAT correction with ed=0.08 (≥ 0.07 floor) must not be filtered"
    )


def test_format_drafting_floor_passes_larger_ed_corrections(fresh_brain):
    """FORMAT/DRAFTING corrections with ed ≥ 0.07 must NOT be filtered."""
    brain = fresh_brain
    # Multi-word restructure in DRAFTING; edit distance should exceed 0.07.
    draft = "Maybe we could perhaps consider thinking about simplifying this."
    final = "Simplify this."
    result = brain.correct(draft, final, category="DRAFTING", session=11)
    assert result.get("low_signal_filtered") is not True, (
        f"Expected substantial DRAFTING edit to pass; ed={result.get('edit_distance')}"
    )


def test_security_accuracy_always_pass_low_ed(fresh_brain):
    """SECURITY/ACCURACY corrections pass regardless of severity or edit distance."""
    brain = fresh_brain
    # Tiny but semantically critical: "not" inserted changes meaning entirely.
    draft = "Users are allowed to delete other users' accounts."
    final = "Users are not allowed to delete other users' accounts."
    for cat in ("SECURITY", "ACCURACY"):
        result = brain.correct(draft, final, category=cat, session=20)
        assert result.get("low_signal_filtered") is not True, (
            f"{cat} correction was incorrectly filtered as low-signal"
        )


def test_non_format_drafting_keeps_original_floor(fresh_brain):
    """Categories outside FORMAT/DRAFTING still use the 0.04 floor, not 0.07."""
    brain = fresh_brain
    # TONE edit above 0.04 but below 0.07 — should NOT be filtered.
    draft = (
        "We are unable to process your request at this moment in time and "
        "we apologize for the inconvenience this has caused you today."
    )
    final = (
        "We cannot process your request right now and we are sorry for the "
        "inconvenience this has caused you today."
    )
    result = brain.correct(draft, final, category="TONE", session=21)
    # ed is likely above 0.04 for this rewrite; should pass as signal
    assert result.get("low_signal_filtered") is not True, (
        f"TONE correction above 0.04 floor should not be filtered; ed={result.get('edit_distance')}"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
