"""Backward-compat shim. Canonical: gradata.patterns.rule_engine"""
from gradata.patterns.rule_engine import (  # noqa: F401
    AppliedRule,
    apply_rules,
    filter_by_scope,
    format_rules_for_prompt,
)
