"""Deprecated import shim for rules distillation algorithms."""

from __future__ import annotations

import warnings

warnings.warn(
    "gradata.enhancements.graduation.rules_distillation is deprecated; "
    "import gradata.enhancements.experimental.rules_distillation instead.",
    DeprecationWarning,
    stacklevel=2,
)

from gradata.enhancements.experimental.rules_distillation import (  # noqa: E402
    DistillationProposal,
    LessonEntry,
    _check_coverage,
    find_distillation_candidates,
    format_proposals,
)

__all__ = [
    "DistillationProposal",
    "LessonEntry",
    "_check_coverage",
    "find_distillation_candidates",
    "format_proposals",
]
