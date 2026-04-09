"""
Self-Healing Engine — Detects rule failures, generates patches, gates them through graduation.

When a RULE (confidence >= 0.80) fails to prevent a correction it covers,
this module:
  1. Detects the failure (detect_rule_failure)
  2. Generates a candidate patch via deterministic heuristic (generate_patch_candidate)
  3. Gates the candidate via retroactive test (retroactive_test)
  4. If it passes, enters the graduation pipeline as INSTINCT

Architecture: LLM-whim as diagnostician, pipeline as validator. Nothing
touches production rules without surviving graduation.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gradata._types import Lesson

_log = logging.getLogger("gradata.self_healing")

# Only RULE state with confidence >= this threshold triggers self-healing
DEFAULT_MIN_CONFIDENCE = 0.80
# States that are alive and should be checked for failures
_ACTIVE_STATES = {"RULE"}


def detect_rule_failure(
    lessons: list[Lesson],
    correction_category: str,
    correction_description: str,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    memory_context: dict | None = None,
) -> dict | None:
    """Check if an existing RULE covers this correction category.

    If a RULE with confidence >= min_confidence exists for this category,
    it should have prevented this correction. Its failure to do so is a
    RULE_FAILURE event.

    Args:
        lessons: All current lessons from the brain.
        correction_category: Category of the correction (e.g. "TONE").
        correction_description: What the correction was about.
        min_confidence: Minimum confidence for a rule to be considered
            (default 0.80 -- rules below this are still maturing).
        memory_context: Optional dict of active memories/domain context
            at the time of failure. Captured for richer diagnosis.

    Returns:
        Dict with failure details if a covering rule was found, None otherwise.
    """
    from gradata._types import LessonState

    cat = correction_category.upper()
    candidates = [
        l for l in lessons
        if l.state == LessonState.RULE
        and l.confidence >= min_confidence
        and l.category.upper() == cat
    ]

    if not candidates:
        return None

    # Pick the highest-confidence rule -- it's the one that should have caught this
    failed_rule = max(candidates, key=lambda l: l.confidence)

    result = {
        "failed_rule_category": cat,
        "failed_rule_description": failed_rule.description,
        "failed_rule_confidence": failed_rule.confidence,
        "failed_rule_fire_count": failed_rule.fire_count,
        "correction_description": correction_description,
    }
    if memory_context:
        result["memory_context"] = memory_context

    return result


def apply_patch(
    lessons: list[Lesson],
    category: str,
    old_description: str,
    new_description: str,
) -> Lesson | None:
    """Find and patch a rule's description. Returns the patched lesson or None.

    Preserves: confidence, fire_count, state, date, all metadata.
    Changes: description only.
    """
    cat = category.upper()
    for lesson in lessons:
        if (lesson.category.upper() == cat
                and lesson.description == old_description):
            lesson.description = new_description
            return lesson
    return None


def retroactive_test(
    original_rule_desc: str,
    proposed_patch_desc: str,
    correction_description: str,
) -> dict:
    """Gate: does the proposed patch's DELTA cover the failure?

    Compares the *new content added by the patch* (the delta between
    original and proposed) against the correction description. This tests
    whether the qualifying language the patch introduces is relevant to
    the failure context -- not just whether the whole rule overlaps.

    No LLM calls. The failure record IS the test.

    Returns:
        {"passes": bool, "delta_score": float, "delta_text": str, "reason": str}
    """
    if proposed_patch_desc.strip() == original_rule_desc.strip():
        return {
            "passes": False,
            "delta_score": 0.0,
            "delta_text": "",
            "reason": "Patch identical to original rule -- no improvement",
        }

    # Extract the delta: words in the patch that aren't in the original
    original_words = set(original_rule_desc.lower().split())
    patch_words = proposed_patch_desc.lower().split()
    delta_words = [w for w in patch_words if w not in original_words]
    delta_text = " ".join(delta_words)

    if not delta_text.strip():
        return {
            "passes": False,
            "delta_score": 0.0,
            "delta_text": "",
            "reason": "No new content in patch",
        }

    # Check if the delta is relevant to the correction
    # Use both TF-IDF similarity and simple word-stem overlap for short texts
    from gradata.enhancements.similarity import best_similarity
    sim = best_similarity(delta_text, correction_description)

    # Fallback: word-stem overlap (handles "emails" vs "email", short deltas)
    delta_stems = {w[:5] for w in delta_text.lower().split() if len(w) >= 3}
    correction_stems = {w[:5] for w in correction_description.lower().split() if len(w) >= 3}
    stem_overlap = len(delta_stems & correction_stems) / max(len(delta_stems), 1)
    score = max(sim, stem_overlap)

    threshold = 0.20  # Lower threshold since delta is shorter text
    passes = score >= threshold

    return {
        "passes": passes,
        "delta_score": round(score, 3),
        "delta_text": delta_text,
        "reason": "Patch delta covers failure" if passes else f"Delta irrelevant ({score:.3f} < {threshold})",
    }
