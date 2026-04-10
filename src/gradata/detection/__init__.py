"""Detection layer — behavioral signal extraction."""

from __future__ import annotations

from gradata.detection.addition_pattern import (
    AdditionTracker,
    classify_addition,
    is_addition,
)
from gradata.detection.correction_conflict import (
    ConflictTracker,
    detect_conflict,
    extract_diff_tokens,
)
from gradata.detection.intent_classifier import CorrectionIntent, classify_intent
from gradata.detection.mode_classifier import MODE_CATEGORY_MAP, classify_mode

__all__ = [
    "MODE_CATEGORY_MAP",
    "AdditionTracker",
    "ConflictTracker",
    "CorrectionIntent",
    "classify_addition",
    "classify_intent",
    "classify_mode",
    "detect_conflict",
    "extract_diff_tokens",
    "is_addition",
]
