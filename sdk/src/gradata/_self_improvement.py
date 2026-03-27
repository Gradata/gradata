"""Backward-compat shim. Tries gradata_cloud first, then enhancements, then stubs."""
from gradata._types import Lesson, LessonState  # noqa: F401

try:
    from gradata_cloud.graduation.self_improvement import (  # noqa: F401
        ACCEPTANCE_BONUS, CONTRADICTION_PENALTY, INITIAL_CONFIDENCE,
        MIN_APPLICATIONS_FOR_PATTERN, MIN_APPLICATIONS_FOR_RULE,
        MISFIRE_PENALTY, PATTERN_THRESHOLD, RULE_THRESHOLD,
        SEVERITY_WEIGHTS, SURVIVAL_BONUS, SURVIVAL_SEVERITY_WEIGHTS,
        UNTESTABLE_SESSION_LIMIT,
        compute_learning_velocity, format_lessons, graduate,
        parse_lessons, update_confidence,
    )
except ImportError:
    try:
        from gradata.enhancements.self_improvement import (  # noqa: F401
            ACCEPTANCE_BONUS, CONTRADICTION_PENALTY, INITIAL_CONFIDENCE,
            MIN_APPLICATIONS_FOR_PATTERN, MIN_APPLICATIONS_FOR_RULE,
            MISFIRE_PENALTY, PATTERN_THRESHOLD, RULE_THRESHOLD,
            SEVERITY_WEIGHTS, SURVIVAL_BONUS, SURVIVAL_SEVERITY_WEIGHTS,
            UNTESTABLE_SESSION_LIMIT,
            compute_learning_velocity, format_lessons, graduate,
            parse_lessons, update_confidence,
        )
    except ImportError:
        # Open source mode: graduation not available locally
        ACCEPTANCE_BONUS = 0.10
        CONTRADICTION_PENALTY = -0.15
        INITIAL_CONFIDENCE = 0.30
        MIN_APPLICATIONS_FOR_PATTERN = 3
        MIN_APPLICATIONS_FOR_RULE = 5
        MISFIRE_PENALTY = -0.20
        PATTERN_THRESHOLD = 0.60
        RULE_THRESHOLD = 0.90
        SURVIVAL_BONUS = 0.10
        UNTESTABLE_SESSION_LIMIT = 20

        # Severity multipliers for contradiction penalty
        # A typo fix should barely dent confidence; a rewrite should hit hard
        SEVERITY_WEIGHTS = {
            "trivial": 0.15,     # typo fix: -0.15 * 0.15 = -0.02
            "minor": 0.40,       # word swap: -0.15 * 0.40 = -0.06
            "moderate": 0.70,    # sentence rewrite: -0.15 * 0.70 = -0.10
            "major": 1.00,       # significant change: -0.15 * 1.00 = -0.15
            "rewrite": 1.30,     # complete rewrite: -0.15 * 1.30 = -0.20
        }

        # Severity multipliers for survival bonus
        # Preventing a trivial mistake is less evidence than preventing a major one
        SURVIVAL_SEVERITY_WEIGHTS = {
            "trivial": 0.30,     # +0.10 * 0.30 = +0.03
            "minor": 0.60,       # +0.10 * 0.60 = +0.06
            "moderate": 0.80,    # +0.10 * 0.80 = +0.08
            "major": 1.00,       # +0.10 * 1.00 = +0.10
            "rewrite": 1.20,     # +0.10 * 1.20 = +0.12
        }

        def compute_learning_velocity(*args, **kwargs):
            return 0.0

        def format_lessons(*args, **kwargs):
            return ""

        def graduate(*args, **kwargs):
            return []

        def parse_lessons(*args, **kwargs):
            return []

        def update_confidence(*args, **kwargs):
            return 0.0
