"""Backward-compat shim. Canonical locations:
  - Types: gradata._types
  - Functions/constants: gradata.enhancements.self_improvement
"""
from gradata._types import Lesson, LessonState  # noqa: F401
from gradata.enhancements.self_improvement import (  # noqa: F401
    ACCEPTANCE_BONUS,
    CONTRADICTION_PENALTY,
    INITIAL_CONFIDENCE,
    MIN_APPLICATIONS_FOR_PATTERN,
    MIN_APPLICATIONS_FOR_RULE,
    MISFIRE_PENALTY,
    PATTERN_THRESHOLD,
    RULE_THRESHOLD,
    SURVIVAL_BONUS,
    UNTESTABLE_SESSION_LIMIT,
    compute_learning_velocity,
    format_lessons,
    graduate,
    parse_lessons,
    update_confidence,
)
