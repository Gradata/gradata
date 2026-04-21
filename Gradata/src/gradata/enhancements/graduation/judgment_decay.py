"""
Judgment Decay — Confidence Decay for Unused Lessons
====================================================
Layer 1 Enhancement: imports from patterns/ (memory, reflection)

Ensures lessons that are not being used gradually lose confidence,
preventing knowledge bloat. Lessons that are actively applied get
reinforced. Lessons with zero applications for extended periods
are flagged UNTESTABLE and archived.

This module provides the ALGORITHM only (pure computation, no I/O).
The brain-layer wiring (file reads, DB queries, event emission) stays
in brain/scripts/judgment_decay.py which calls these functions.

Decay rules:
  1. RULE tier: immune to decay (proven behavioral rules are permanent)
  2. Per idle session: -0.02 confidence (floor: 0.10)
  3. Per applied session: +0.05 reinforcement (capped at tier ceiling)
  4. 20+ idle sessions with 0 applications AND 0 corrections → UNTESTABLE
  5. Lessons added in the current session: skip decay
  6. Session-type-aware: decay only ticks on sessions where the lesson's
     category was testable (e.g., DRAFTING lessons ignore system sessions)

Research backing:
  - Decay rate 0.02/session: Ebbinghaus forgetting curve adapted for
    discrete session intervals (not continuous time)
  - Reinforcement bonus 0.05: Sub-survival bonus (0.10) to prevent
    gaming via trivial applications
  - UNTESTABLE threshold 20: Aligned with SPEC Section 1 kill switches
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from gradata.enhancements.self_improvement import (
    PATTERN_THRESHOLD,
    Lesson,
    LessonState,
)

# Decay constants
DECAY_PER_IDLE_SESSION = 0.02
CONFIDENCE_FLOOR = 0.10
REINFORCEMENT_BONUS = 0.05
INSTINCT_CEILING = 0.59
PATTERN_CEILING = 0.89
UNTESTABLE_THRESHOLD = 20

# ---------------------------------------------------------------------------
# Session-Type-Aware Decay
# ---------------------------------------------------------------------------
# Maps lesson categories to the session types where they can be tested.
# A lesson is only decayed during sessions where it had a chance to fire.
# This prevents sales lessons from decaying during system sessions and vice versa.
#
# "universal" categories decay in ALL session types (they're always testable).
# Unknown categories default to universal (safe fallback: decay applies).

CATEGORY_SESSION_TYPES: dict[str, set[str]] = {
    # Sales/pipeline categories — only testable in sales sessions
    "DRAFTING": {"sales", "pipeline"},
    "POSITIONING": {"sales", "pipeline"},
    "PRICING": {"sales", "pipeline"},
    "DEMO_PREP": {"sales", "pipeline"},
    "COMMUNICATION": {"sales", "pipeline"},
    "APIFY": {"sales", "pipeline"},
    "LEADS": {"sales", "pipeline"},
    # System/architecture categories — only testable in system sessions
    "ARCHITECTURE": {"system"},
    # Universal categories — testable in any session type
    "ACCURACY": {"sales", "system", "pipeline", "mixed"},
    "PROCESS": {"sales", "system", "pipeline", "mixed"},
    "THOROUGHNESS": {"sales", "system", "pipeline", "mixed"},
    "STARTUP": {"sales", "system", "pipeline", "mixed"},
    "DATA_INTEGRITY": {"sales", "system", "pipeline", "mixed"},
    "CONTEXT": {"sales", "system", "pipeline", "mixed"},
    "CONSTRAINT": {"sales", "system", "pipeline", "mixed"},
    "PRESENTATION": {"sales", "system", "pipeline", "mixed"},
}

# All known session types (for universal fallback)
ALL_SESSION_TYPES = {"sales", "system", "pipeline", "mixed"}


def is_category_testable(category: str, session_type: str | None) -> bool:
    """Check if a lesson category is testable in the given session type.

    Args:
        category: Lesson category (e.g., "DRAFTING", "ARCHITECTURE")
        session_type: Current session type ("sales", "system", "pipeline", "mixed").
            If None, all categories are testable (backward compat).

    Returns:
        True if the category can be tested in this session type.
    """
    if session_type is None:
        return True  # backward compat: no filtering
    testable_types = CATEGORY_SESSION_TYPES.get(category.upper(), ALL_SESSION_TYPES)
    return session_type.lower() in testable_types


@dataclass
class DecayResult:
    """Result of applying decay to a single lesson."""

    category: str
    tier: str
    old_confidence: float
    new_confidence: float
    action: str  # "decayed" | "reinforced" | "archived" | "skipped"
    reason: str


def compute_decay(
    lesson: Lesson,
    sessions_since_applied: int,
    was_applied_this_session: bool,
    total_idle_sessions: int,
    session_type: str | None = None,
) -> DecayResult:
    """Compute the decay/reinforcement for a single lesson.

    Pure function — no I/O, no side effects. The caller is responsible
    for applying the result to the lesson and persisting it.

    Args:
        lesson: The lesson to evaluate
        sessions_since_applied: How many TESTABLE sessions since this lesson was last applied
        was_applied_this_session: Whether the lesson was applied in the current session
        total_idle_sessions: Total TESTABLE sessions with 0 applications AND 0 matching corrections
        session_type: Current session type ("sales", "system", "pipeline", "mixed").
            If None, all categories are testable (backward compat).
            When set, lessons whose category isn't testable in this session type
            are skipped entirely — no decay, no reinforcement, no idle tick.

    Returns:
        DecayResult with the computed action and new confidence
    """
    tier = lesson.state.value
    old_conf = lesson.confidence

    def _result(new_conf: float, action: str, reason: str) -> DecayResult:
        return DecayResult(
            category=lesson.category,
            tier=tier,
            old_confidence=old_conf,
            new_confidence=new_conf,
            action=action,
            reason=reason,
        )

    # Session-type filter: skip lessons that can't be tested in this session type
    if not is_category_testable(lesson.category, session_type):
        return _result(
            old_conf, "skipped", f"{lesson.category} not testable in {session_type} session"
        )

    # RULE tier: immune to decay
    if lesson.state == LessonState.RULE:
        return _result(old_conf, "skipped", "RULE tier is immune to decay")

    # Applied this session → reinforce
    if was_applied_this_session:
        ceiling = INSTINCT_CEILING if lesson.state == LessonState.INSTINCT else PATTERN_CEILING
        new_conf = round(min(ceiling, old_conf + REINFORCEMENT_BONUS), 2)
        return _result(new_conf, "reinforced", f"applied this session (+{REINFORCEMENT_BONUS})")

    # UNTESTABLE check: too many idle sessions
    if total_idle_sessions >= UNTESTABLE_THRESHOLD:
        return _result(
            0.0,
            "archived",
            f"{total_idle_sessions} idle sessions >= {UNTESTABLE_THRESHOLD} threshold",
        )

    # Standard decay
    if sessions_since_applied > 0:
        penalty = DECAY_PER_IDLE_SESSION * sessions_since_applied
        new_conf = round(max(CONFIDENCE_FLOOR, old_conf - penalty), 2)
        return _result(
            new_conf, "decayed", f"{sessions_since_applied} idle sessions (-{penalty:.2f})"
        )

    # No change needed
    return _result(old_conf, "skipped", "no idle sessions detected")


def compute_batch_decay(
    lessons: list[Lesson],
    application_data: dict[str, dict[str, Any]],
    current_session: int,
    session_type: str | None = None,
) -> list[DecayResult]:
    """Compute decay for a batch of lessons.

    Args:
        lessons: All active lessons
        application_data: Map of category -> {
            "last_applied_session": int,
            "applied_this_session": bool,
            "total_idle_sessions": int,
        }
        current_session: Current session number
        session_type: Current session type ("sales", "system", "pipeline", "mixed").
            Passed through to compute_decay for session-type-aware filtering.

    Returns:
        List of DecayResults, one per lesson
    """
    results = []
    for lesson in lessons:
        cat = lesson.category
        app = application_data.get(cat, {})
        last_applied = app.get("last_applied_session", 0)
        applied_this = app.get("applied_this_session", False)
        total_idle = app.get("total_idle_sessions", 0)
        sessions_since = current_session - last_applied if last_applied > 0 else 0

        result = compute_decay(
            lesson,
            sessions_since,
            applied_this,
            total_idle,
            session_type=session_type,
        )
        results.append(result)

    return results
