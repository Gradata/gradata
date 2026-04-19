"""Public API re-exports. ``_scoring`` (difficulty/reliability/scope), ``_formatting``
(dedup/merge/entropy/injection), ``_engine`` (apply_rules, filter_by_scope, TTL, AppliedRule)."""

from ._engine import (
    DEFAULT_TTL_SESSIONS,
    AppliedRule,
    _make_rule_id,
    apply_rules,
    apply_rules_with_tree,
    demote_stale_rules,
)
from ._formatting import (
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
from ._scoring import (
    _beta_ppf_05,
    _difficulty_from_lesson,
    beta_domain_reliability,
    compute_rule_difficulty,
    compute_scope_weight,
    detect_task_type,
    effective_confidence,
    is_rule_disabled_for_domain,
)

__all__ = [
    "DEFAULT_TTL_SESSIONS",
    "AppliedRule",
    "_beta_ppf_05",
    "_difficulty_from_lesson",
    "_make_rule_id",
    "_ordering_entropy",
    "_rule_set_hash",
    "apply_rules",
    "apply_rules_with_tree",
    "beta_domain_reliability",
    "capture_example_from_correction",
    "choose_entropy_ordering",
    "clear_ordering_cache",
    "compute_rule_difficulty",
    "compute_scope_weight",
    "demote_stale_rules",
    "detect_task_type",
    "effective_confidence",
    "format_rule_constitutional",
    "format_rules_for_prompt",
    "format_rules_styled",
    "is_rule_disabled_for_domain",
    "merge_related_rules",
]
