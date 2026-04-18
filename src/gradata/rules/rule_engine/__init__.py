"""
gradata.rules.rule_engine — public API (backward-compatible re-exports).
=========================================================================
The module was split into submodules for maintainability:

  _scoring.py    — difficulty, reliability, scope weighting, transfer scope
  _formatting.py — dedup, merge, entropy ordering, prompt injection
  _engine.py     — apply_rules, filter_by_scope, TTL demotion, AppliedRule

All public symbols remain importable from this package, so existing callers
(``from gradata.rules.rule_engine import apply_rules``) continue to work
without modification.
"""

from ._engine import (
    DEFAULT_TTL_SESSIONS,
    _make_rule_id,
    apply_rules,
    apply_rules_with_tree,
    AppliedRule,
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
    "AppliedRule",
    "DEFAULT_TTL_SESSIONS",
    "_make_rule_id",
    "apply_rules",
    "apply_rules_with_tree",
    "demote_stale_rules",
    "_beta_ppf_05",
    "_difficulty_from_lesson",
    "beta_domain_reliability",
    "compute_rule_difficulty",
    "compute_scope_weight",
    "detect_task_type",
    "effective_confidence",
    "is_rule_disabled_for_domain",
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
