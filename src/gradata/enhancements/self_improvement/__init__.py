"""Procedural Memory — INSTINCT→PATTERN→RULE graduation pipeline. Confidence
scoring, lesson parsing, FSRS-inspired graduation, adversarial validation.
Cloud (``gradata_cloud.graduation.self_improvement``) layers FSRS scheduling
+ multi-brain optimization. ``_confidence.py``: math/parse/format/update;
``_graduation.py``: gate+graduate. SDK Layer 1 (imports patterns + _types).
"""

# Re-export everything that was previously importable from the flat module.
# All of these imports MUST keep working:
#   from gradata.enhancements.self_improvement import X

# Lesson and LessonState are imported into _confidence.py from gradata._types;
# they are accessible as self_improvement.Lesson etc. via the namespace, but
# callers that do `from gradata.enhancements.self_improvement import Lesson`
# need them explicitly re-exported here.
from ..._types import (
    CorrectionType,
    Lesson,
    LessonState,
    RuleMetadata,
    transition,
)
from ._confidence import (
    ACCEPTANCE_BONUS,
    CATEGORY_SESSION_MAP,
    CONTRADICTION_ACCELERATION,
    CONTRADICTION_COOLING_SESSIONS,
    CONTRADICTION_PENALTY,
    CONTRADICTION_SEVERITY_BOOST,
    CONTRADICTION_STREAK_STEP,
    INITIAL_CONFIDENCE,
    KILL_LIMITS,
    MACHINE_ACCEPTANCE_BONUS,
    MACHINE_CONTRADICTION_PENALTY,
    MACHINE_KILL_LIMITS,
    MACHINE_SEVERITY_WEIGHTS,
    MAX_PER_SESSION_DELTA,
    MAX_PER_STEP_PENALTY,
    MIN_APPLICATIONS_FOR_PATTERN,
    MIN_APPLICATIONS_FOR_RULE,
    MISFIRE_PENALTY,
    PATTERN_THRESHOLD,
    PREFERENCE_DECAY_DAMPER,
    RULE_THRESHOLD,
    SEVERITY_WEIGHTS,
    SURVIVAL_BONUS,
    SURVIVAL_SEVERITY_WEIGHTS,
    _classify_correction_direction,
    _detect_machine_context,
    _is_testable,
    _normalize_severity,
    compute_learning_velocity,
    detect_correction_poisoning,
    format_lessons,
    fsrs_bonus,
    fsrs_penalty,
    get_maturity_phase,
    is_hook_enforced,
    parse_lessons,
    propagate_confidence,
    update_confidence,
)
from ._graduation import (
    _passes_beta_lb_gate,
    graduate,
)

# Backward-compat lazy re-exports (symbols moved to other focused modules).
# Preserved from the original flat-module __getattr__.


def __getattr__(name: str):  # type: ignore[return]
    _PIPELINE_NAMES = {
        "PipelineResult",
        "run_rule_pipeline",
        "_generate_skill_file",
        "review_generated_skill",
    }
    _CAUSAL_NAMES = {"CausalRelation", "CausalLink", "CausalChain"}
    _CLUSTER_NAMES = {
        "RuleCluster",
        "detect_contradictions",
        "cluster_rules",
        "promote_instinct_clusters",
    }

    if name in _PIPELINE_NAMES:
        from .. import rule_pipeline

        return getattr(rule_pipeline, name)
    if name in _CAUSAL_NAMES:
        from .. import causal_chains

        return getattr(causal_chains, name)
    if name in _CLUSTER_NAMES:
        from .. import clustering

        return getattr(clustering, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
