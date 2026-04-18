"""Backward-compat shim -- moved to _brain_manifest."""
from ._brain_manifest import (
    _behavioral_contract,
    _correction_rate_trend,
    _lesson_distribution,
    _memory_composition,
    _outcome_correlation,
    _quality_metrics,
    _rag_status,
    _temporal_provenance,
)

__all__ = [
    "_behavioral_contract",
    "_correction_rate_trend",
    "_lesson_distribution",
    "_memory_composition",
    "_outcome_correlation",
    "_quality_metrics",
    "_rag_status",
    "_temporal_provenance",
]
