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
