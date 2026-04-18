"""Backward-compat shim — moved to rule_pipeline."""
from .rule_pipeline import (
    TOOL_RULE_MATRIX,
    RuleVerification,
    auto_detect_verification,
    ensure_table,
    get_relevant_rules,
    get_verification_stats,
    log_verification,
    should_verify,
    verify_rules,
)

__all__ = [
    "TOOL_RULE_MATRIX",
    "RuleVerification",
    "auto_detect_verification",
    "ensure_table",
    "get_relevant_rules",
    "get_verification_stats",
    "log_verification",
    "should_verify",
    "verify_rules",
]
