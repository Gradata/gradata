"""
Tests for severity-weighted graduation confidence.

Verifies that edit distance severity labels scale confidence
updates instead of applying flat-rate penalties/bonuses.

Tests work against whichever self_improvement module is available:
- gradata_cloud.graduation.self_improvement (proprietary, CI)
- gradata.enhancements.self_improvement (packaged engine)
- gradata._self_improvement stubs (open source, constants only)
"""

import pytest

from gradata._types import Lesson, LessonState
from gradata._self_improvement import (
    SEVERITY_WEIGHTS,
    SURVIVAL_SEVERITY_WEIGHTS,
    SURVIVAL_BONUS,
    CONTRADICTION_PENALTY,
)

# Try to get the real engine functions; skip functional tests if only stubs
_HAS_ENGINE = False
try:
    from gradata._self_improvement import update_confidence as _uc_check
    # Stubs return 0.0; real engine returns list[Lesson]
    _dummy = Lesson("2026-01-01", LessonState.INSTINCT, 0.50, "X", "test")
    result = _uc_check([_dummy], [{"category": "X"}])
    _HAS_ENGINE = isinstance(result, list) and len(result) > 0
except Exception:
    _HAS_ENGINE = False

if _HAS_ENGINE:
    from gradata._self_improvement import update_confidence
    try:
        from gradata.enhancements.self_improvement import fsrs_bonus, fsrs_penalty
    except ImportError:
        try:
            from gradata_cloud.graduation.self_improvement import fsrs_bonus, fsrs_penalty
        except ImportError:
            fsrs_bonus = None
            fsrs_penalty = None


def _make_lesson(category: str = "DRAFTING", confidence: float = 0.50) -> Lesson:
    return Lesson(
        date="2026-03-27",
        state=LessonState.INSTINCT if confidence < 0.60 else LessonState.PATTERN,
        confidence=confidence,
        category=category,
        description="Test lesson",
        fire_count=3,
    )


# ---------------------------------------------------------------------------
# Constants tests (always pass -- these are in stubs too)
# ---------------------------------------------------------------------------

class TestSeverityWeightsExist:
    """Severity weight dicts are importable and complete."""

    def test_contradiction_weights_keys(self):
        for label in ("trivial", "minor", "moderate", "major", "rewrite"):
            assert label in SEVERITY_WEIGHTS

    def test_survival_weights_keys(self):
        for label in ("trivial", "minor", "moderate", "major", "rewrite"):
            assert label in SURVIVAL_SEVERITY_WEIGHTS

    def test_contradiction_ordering(self):
        """More severe corrections should have higher multipliers."""
        assert SEVERITY_WEIGHTS["trivial"] < SEVERITY_WEIGHTS["minor"]
        assert SEVERITY_WEIGHTS["minor"] < SEVERITY_WEIGHTS["moderate"]
        assert SEVERITY_WEIGHTS["moderate"] < SEVERITY_WEIGHTS["major"]
        assert SEVERITY_WEIGHTS["major"] < SEVERITY_WEIGHTS["rewrite"]

    def test_survival_ordering(self):
        """More severe sessions should give higher survival bonus."""
        assert SURVIVAL_SEVERITY_WEIGHTS["trivial"] < SURVIVAL_SEVERITY_WEIGHTS["minor"]
        assert SURVIVAL_SEVERITY_WEIGHTS["minor"] < SURVIVAL_SEVERITY_WEIGHTS["moderate"]
        assert SURVIVAL_SEVERITY_WEIGHTS["moderate"] < SURVIVAL_SEVERITY_WEIGHTS["major"]
        assert SURVIVAL_SEVERITY_WEIGHTS["major"] < SURVIVAL_SEVERITY_WEIGHTS["rewrite"]

    def test_trivial_penalty_math(self):
        """Trivial: base * 0.15 should yield roughly -0.02 from -0.15 base."""
        effective = abs(CONTRADICTION_PENALTY) * SEVERITY_WEIGHTS["trivial"]
        # With legacy constants: 0.15 * 0.15 = 0.0225
        assert 0.01 < effective < 0.05

    def test_rewrite_penalty_math(self):
        """Rewrite: base * 1.30 should yield roughly -0.20 from -0.15 base."""
        effective = abs(CONTRADICTION_PENALTY) * SEVERITY_WEIGHTS["rewrite"]
        # With legacy constants: 0.15 * 1.30 = 0.195
        assert effective > 0.15

    def test_trivial_survival_math(self):
        """Trivial survival: +0.10 * 0.30 = +0.03."""
        effective = SURVIVAL_BONUS * SURVIVAL_SEVERITY_WEIGHTS["trivial"]
        assert 0.02 < effective < 0.05

    def test_major_survival_math(self):
        """Major survival: +0.10 * 1.00 = +0.10 (unchanged)."""
        effective = SURVIVAL_BONUS * SURVIVAL_SEVERITY_WEIGHTS["major"]
        assert abs(effective - SURVIVAL_BONUS) < 0.001


# ---------------------------------------------------------------------------
# Functional tests (require real engine, skipped on stub-only installs)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _HAS_ENGINE, reason="Real graduation engine not available")
class TestContradictionSeverity:
    """Contradiction penalties should scale by severity label."""

    def test_trivial_correction_small_penalty(self):
        lesson = _make_lesson(confidence=0.50)
        original = lesson.confidence
        update_confidence(
            [lesson],
            corrections_this_session=[{"category": "DRAFTING"}],
            severity_data={"DRAFTING": "trivial"},
        )
        drop = original - lesson.confidence
        assert drop > 0, "Should penalize"
        assert drop < 0.05, f"Trivial penalty too large: {drop}"

    def test_rewrite_correction_large_penalty(self):
        lesson = _make_lesson(confidence=0.50)
        original = lesson.confidence
        update_confidence(
            [lesson],
            corrections_this_session=[{"category": "DRAFTING"}],
            severity_data={"DRAFTING": "rewrite"},
        )
        drop = original - lesson.confidence
        assert drop > 0.10, f"Rewrite penalty too small: {drop}"

    def test_major_correction_full_penalty(self):
        lesson = _make_lesson(confidence=0.50)
        original = lesson.confidence
        update_confidence(
            [lesson],
            corrections_this_session=[{"category": "DRAFTING"}],
            severity_data={"DRAFTING": "major"},
        )
        drop = original - lesson.confidence
        if fsrs_penalty:
            base_penalty = fsrs_penalty(0.50)
            assert abs(drop - base_penalty) < 0.02, (
                f"Major should match base: drop={drop}, base={base_penalty}"
            )
        else:
            assert drop > 0

    def test_trivial_vs_rewrite_ratio(self):
        """Rewrite correction should penalize far more than trivial."""
        lesson_t = _make_lesson(confidence=0.50)
        lesson_r = _make_lesson(confidence=0.50)
        update_confidence(
            [lesson_t],
            corrections_this_session=[{"category": "DRAFTING"}],
            severity_data={"DRAFTING": "trivial"},
        )
        update_confidence(
            [lesson_r],
            corrections_this_session=[{"category": "DRAFTING"}],
            severity_data={"DRAFTING": "rewrite"},
        )
        drop_t = 0.50 - lesson_t.confidence
        drop_r = 0.50 - lesson_r.confidence
        assert drop_r > drop_t * 4, (
            f"Rewrite drop ({drop_r}) should be >> trivial drop ({drop_t})"
        )


@pytest.mark.skipif(not _HAS_ENGINE, reason="Real graduation engine not available")
class TestSurvivalSeverity:
    """Survival bonuses should scale by the severity of corrections elsewhere."""

    def test_trivial_session_small_bonus(self):
        lesson = _make_lesson(category="ACCURACY", confidence=0.50)
        original = lesson.confidence
        update_confidence(
            [lesson],
            corrections_this_session=[{"category": "DRAFTING"}],
            severity_data={"DRAFTING": "trivial"},
        )
        gain = lesson.confidence - original
        assert gain > 0, "Should get survival bonus"
        assert gain < 0.05, f"Trivial survival bonus too large: {gain}"

    def test_major_session_full_bonus(self):
        lesson = _make_lesson(category="ACCURACY", confidence=0.50)
        original = lesson.confidence
        update_confidence(
            [lesson],
            corrections_this_session=[{"category": "DRAFTING"}],
            severity_data={"DRAFTING": "major"},
        )
        gain = lesson.confidence - original
        if fsrs_bonus:
            base = fsrs_bonus(0.50)
            assert abs(gain - base) < 0.02, (
                f"Major survival should match base: gain={gain}, base={base}"
            )
        else:
            assert gain > 0

    def test_rewrite_session_boosted_bonus(self):
        lesson = _make_lesson(category="ACCURACY", confidence=0.50)
        original = lesson.confidence
        update_confidence(
            [lesson],
            corrections_this_session=[{"category": "DRAFTING"}],
            severity_data={"DRAFTING": "rewrite"},
        )
        gain = lesson.confidence - original
        if fsrs_bonus:
            base = fsrs_bonus(0.50)
            assert gain > base, (
                f"Rewrite survival ({gain}) should exceed base ({base})"
            )
        else:
            assert gain > 0


@pytest.mark.skipif(not _HAS_ENGINE, reason="Real graduation engine not available")
class TestBackwardCompat:
    """Without severity_data, behavior should use moderate default."""

    def test_no_severity_data_still_works(self):
        lesson = _make_lesson(confidence=0.50)
        original = lesson.confidence
        update_confidence(
            [lesson],
            corrections_this_session=[{"category": "DRAFTING"}],
        )
        assert lesson.confidence < original

    def test_inline_severity_from_correction(self):
        """Corrections carrying severity_label inline should be used."""
        lesson = _make_lesson(confidence=0.50)
        original = lesson.confidence
        update_confidence(
            [lesson],
            corrections_this_session=[
                {"category": "DRAFTING", "severity_label": "trivial"}
            ],
        )
        drop = original - lesson.confidence
        assert drop < 0.05, f"Inline trivial penalty too large: {drop}"
