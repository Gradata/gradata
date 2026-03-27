"""Backward-compat shim. Canonical: gradata.patterns.rule_tracker"""
from gradata.patterns.rule_tracker import (  # noqa: F401
    get_rule_history,
    get_rule_stats,
    get_session_applications,
    log_application,
)
