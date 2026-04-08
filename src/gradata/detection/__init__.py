"""Detection layer — behavioral signal extraction."""

from gradata.detection.mode_classifier import classify_mode, MODE_CATEGORY_MAP
from gradata.detection.addition_pattern import (
    is_addition,
    classify_addition,
    AdditionTracker,
)
from gradata.detection.correction_conflict import (
    detect_conflict,
    extract_diff_tokens,
    ConflictTracker,
)

__all__ = [
    "classify_mode",
    "MODE_CATEGORY_MAP",
    "is_addition",
    "classify_addition",
    "AdditionTracker",
    "detect_conflict",
    "extract_diff_tokens",
    "ConflictTracker",
]
