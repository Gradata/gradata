"""Backward-compat shim. Canonical: gradata.enhancements.failure_detectors"""
from gradata.enhancements.failure_detectors import (  # noqa: F401
    Alert,
    detect_being_ignored,
    detect_failures,
    detect_overfitting,
    detect_playing_safe,
    detect_regression_to_mean,
    format_alerts,
)
