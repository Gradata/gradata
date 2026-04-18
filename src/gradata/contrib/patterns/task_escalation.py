"""Backward-compat shim — moved to execute_qualify."""
from .execute_qualify import (
    TaskOutcome,
    TaskStatus,
    format_outcome,
    is_actionable,
    report_outcome,
    requires_human,
)

__all__ = [
    "TaskOutcome",
    "TaskStatus",
    "format_outcome",
    "is_actionable",
    "report_outcome",
    "requires_human",
]
