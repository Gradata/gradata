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

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gradata._types import Lesson

# Only RULE state with confidence >= this threshold triggers self-healing
DEFAULT_MIN_CONFIDENCE = 0.80


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
                and lesson.description.strip() == old_description.strip()):
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


def _generate_deterministic_patch(
    rule_description: str,
    correction_description: str,
) -> str:
    """Generate a narrowed rule description without LLM.

    Heuristic: append the correction context as a qualifying clause.
    This is the deterministic fallback. LLM refinement is Phase 2.
    """
    correction_lower = correction_description.lower()
    rule_lower = rule_description.lower()

    # Find words in correction that aren't in the rule -- these are the context
    rule_words = set(rule_lower.split())
    correction_words = set(correction_lower.split())
    new_context_words = correction_words - rule_words - {
        "the", "a", "an", "in", "on", "at", "to", "for", "of", "is", "was",
        "from", "with", "and", "or", "but", "not", "this", "that",
    }

    if not new_context_words:
        return rule_description  # Can't narrow -- return unchanged

    # Take top 3 most informative context words
    context_phrase = " ".join(list(new_context_words)[:3])
    return f"{rule_description} (especially in context: {context_phrase})"


def review_rule_failures(
    failure_events: list[dict],
) -> list[dict]:
    """Analyze RULE_FAILURE events and generate patch candidates.

    Each candidate includes:
      - category, original_description, proposed_description
      - retroactive_test result (must pass to enter pipeline)

    This is the background review fork (Hermes pattern).
    """
    if not failure_events:
        return []

    patches = []
    for event in failure_events:
        data = event.get("data", {})
        category = data.get("failed_rule_category", "")
        original = data.get("failed_rule_description", "")
        correction = data.get("correction_description", "")

        if not category or not original:
            continue

        proposed = _generate_deterministic_patch(original, correction)

        test_result = retroactive_test(original, proposed, correction)

        patches.append({
            "category": category,
            "original_description": original,
            "proposed_description": proposed,
            "correction_description": correction,
            "retroactive_test": test_result,
        })

    return patches


# ── Nudging ────────────────────────────────────────────────────────────

NUDGE_THRESHOLD = 3  # Corrections before nudging


def _find_centroid(descriptions: list[str]) -> str:
    """Find the most representative description (highest avg similarity to others)."""
    if len(descriptions) <= 1:
        return descriptions[0] if descriptions else ""

    from gradata.enhancements.similarity import best_similarity

    best_desc, best_avg = descriptions[0], 0.0
    for desc in descriptions:
        avg_sim = sum(best_similarity(desc, other) for other in descriptions if other != desc)
        avg_sim /= max(len(descriptions) - 1, 1)
        if avg_sim > best_avg:
            best_avg = avg_sim
            best_desc = desc
    return best_desc


def check_nudge_threshold(
    correction_events: list[dict],
    lessons: list[Lesson],
    category: str,
    threshold: int = NUDGE_THRESHOLD,
) -> dict:
    """Check if a category has enough corrections without a covering rule to trigger a nudge.

    When triggered (A+B strategy):
      - Proposes an INSTINCT lesson from the centroid correction (most representative)
      - Marks it pending_approval=True so it won't graduate without validation

    Returns:
        {"should_nudge": bool, "correction_count": int, "centroid_description": str,
         "proposed_lesson": dict | None, ...}
    """
    from gradata._types import LessonState

    cat = category.upper()

    # Collect corrections in this category
    cat_corrections = [
        e for e in correction_events
        if (e.get("data", {}).get("category", "") or "").upper() == cat
    ]
    count = len(cat_corrections)

    # Check if a RULE already covers this category
    existing_rule = next(
        (l for l in lessons
         if l.category.upper() == cat
         and l.state == LessonState.RULE
         and l.confidence >= DEFAULT_MIN_CONFIDENCE),
        None,
    )

    if existing_rule:
        return {
            "should_nudge": False,
            "correction_count": count,
            "centroid_description": "",
            "proposed_lesson": None,
            "existing_rule": existing_rule.description[:200],
            "reason": "Rule already exists for this category",
        }

    should_nudge = count >= threshold
    if not should_nudge:
        return {
            "should_nudge": False,
            "correction_count": count,
            "centroid_description": "",
            "proposed_lesson": None,
            "category": cat,
            "reason": f"Below threshold ({count}/{threshold})",
        }

    # Find centroid: most representative correction description
    descriptions = [
        e.get("data", {}).get("summary", "") or e.get("data", {}).get("description", "")
        for e in cat_corrections
    ]
    descriptions = [d for d in descriptions if d]
    centroid = _find_centroid(descriptions) if descriptions else f"Repeated {cat.lower()} corrections"

    # Propose an INSTINCT lesson with pending_approval
    from gradata.enhancements.self_improvement import INITIAL_CONFIDENCE
    proposed = {
        "state": "INSTINCT",
        "confidence": INITIAL_CONFIDENCE,
        "category": cat,
        "description": centroid,
        "pending_approval": True,
    }

    return {
        "should_nudge": True,
        "correction_count": count,
        "centroid_description": centroid,
        "proposed_lesson": proposed,
        "category": cat,
        "reason": f"{count} corrections, threshold={threshold}",
    }


# ── Scope Narrowing (Phase 2 prep -- capture only) ────────────────────

def narrow_rule_scope(
    rule: Lesson,
    failure_context: dict,
) -> dict:
    """Add a domain exclusion to a rule based on the context where it failed.

    If a rule fires correctly in "sales email" but incorrectly in "casual slack",
    the slack domain gets excluded. This is Phase 2 prep -- captures the signal
    now, full scoped-brains implementation later.

    Args:
        rule: The rule that failed.
        failure_context: Dict with domain/agent_type/memory info from the failure.

    Returns:
        {"narrowed": bool, "new_scope_json": str, ...}
    """
    import json

    domain = failure_context.get("domain", "")
    if not domain:
        return {"narrowed": False, "reason": "No domain in failure context"}

    # Parse existing scope
    existing_scope: dict = {}
    if rule.scope_json:
        try:
            existing_scope = json.loads(rule.scope_json)
        except (json.JSONDecodeError, TypeError):
            existing_scope = {}

    excluded = existing_scope.get("excluded_domains", [])
    if domain in excluded:
        return {"narrowed": False, "reason": f"Domain {domain!r} already excluded"}

    excluded.append(domain)
    existing_scope["excluded_domains"] = excluded

    # Capture memory context if present (memories as scoping signal)
    if failure_context.get("active_memories"):
        memory_exclusions = existing_scope.get("excluded_memory_contexts", [])
        memory_exclusions.append({
            "memories": failure_context["active_memories"],
            "domain": domain,
        })
        existing_scope["excluded_memory_contexts"] = memory_exclusions

    new_scope_json = json.dumps(existing_scope)

    return {
        "narrowed": True,
        "new_scope_json": new_scope_json,
        "excluded_domain": domain,
    }
