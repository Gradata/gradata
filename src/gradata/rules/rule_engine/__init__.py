"""
gradata.rules.rule_engine — public API (backward-compatible re-exports).
=========================================================================
The module was split into submodules for maintainability:

  _models.py     — AppliedRule dataclass
  _scoring.py    — difficulty, reliability, scope weighting, transfer scope
  _formatting.py — dedup, merge, entropy ordering, prompt injection
  _engine.py     — apply_rules, filter_by_scope, TTL demotion, orchestration

All public symbols remain importable from this package, so existing callers
(``from gradata.rules.rule_engine import apply_rules``) continue to work
without modification.
"""

from ._engine import (
    DEFAULT_TTL_SESSIONS,
    _ELIGIBLE_STATES,
    _make_rule_id,
    _tier_label,
    apply_rules,
    apply_rules_with_tree,
    demote_stale_rules,
    filter_by_scope,
)
from ._formatting import (
    _CONSTITUTIONAL_VALUE_MAP,
    _DEFAULT_PERMUTATION_SAMPLES,
    _EXAMPLE_MAX_CHARS,
    _IMPERATIVE_PREFIXES,
    _ORDERING_CACHE,
    _ORDERING_CACHE_MAX,
    _category_entropy,
    _deduplicate_rules,
    _ordering_entropy,
    _rule_set_hash,
    capture_example_from_correction,
    choose_entropy_ordering,
    clear_ordering_cache,
    format_rule_constitutional,
    format_rules_for_prompt,
    format_rules_styled,
    merge_related_rules,
)
from ._models import AppliedRule
from ._scoring import (
    _CT_BOOST,
    _STATE_PRIORITY,
    _TASK_TYPE_PATTERNS,
    _TEAM_SIGNALS,
    _UNIVERSAL_SIGNALS,
    _beta_ppf_05,
    _difficulty_from_lesson,
    beta_domain_reliability,
    classify_transfer_scope,
    compute_rule_difficulty,
    compute_scope_weight,
    detect_task_type,
    effective_confidence,
    is_rule_disabled_for_domain,
    validate_assumptions,
)

__all__ = [
    # models
    "AppliedRule",
    # engine
    "DEFAULT_TTL_SESSIONS",
    "_ELIGIBLE_STATES",
    "_make_rule_id",
    "_tier_label",
    "apply_rules",
    "apply_rules_with_tree",
    "demote_stale_rules",
    "filter_by_scope",
    # scoring
    "_CT_BOOST",
    "_STATE_PRIORITY",
    "_TASK_TYPE_PATTERNS",
    "_TEAM_SIGNALS",
    "_UNIVERSAL_SIGNALS",
    "_beta_ppf_05",
    "_difficulty_from_lesson",
    "beta_domain_reliability",
    "classify_transfer_scope",
    "compute_rule_difficulty",
    "compute_scope_weight",
    "detect_task_type",
    "effective_confidence",
    "is_rule_disabled_for_domain",
    "validate_assumptions",
    # formatting
    "_CONSTITUTIONAL_VALUE_MAP",
    "_DEFAULT_PERMUTATION_SAMPLES",
    "_EXAMPLE_MAX_CHARS",
    "_IMPERATIVE_PREFIXES",
    "_ORDERING_CACHE",
    "_ORDERING_CACHE_MAX",
    "_category_entropy",
    "_deduplicate_rules",
    "_ordering_entropy",
    "_rule_set_hash",
    "capture_example_from_correction",
    "choose_entropy_ordering",
    "clear_ordering_cache",
    "format_rule_constitutional",
    "format_rules_for_prompt",
    "format_rules_styled",
    "merge_related_rules",
]
