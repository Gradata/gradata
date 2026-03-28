"""Backward-compat shim. Tries gradata_cloud first, then enhancements, then stubs."""
from dataclasses import dataclass

try:
    from gradata_cloud.scoring.failure_detectors import (
        Alert,
        detect_being_ignored,
        detect_failures,
        detect_overfitting,
        detect_playing_safe,
        detect_regression_to_mean,
        format_alerts,
    )
except ImportError:
    try:
        from gradata.enhancements.failure_detectors import (
            Alert,
            detect_being_ignored,
            detect_failures,
            detect_overfitting,
            detect_playing_safe,
            detect_regression_to_mean,
            format_alerts,
        )
    except ImportError:
        @dataclass
        class Alert:  # type: ignore[no-redef]
            detector: str = ""
            severity: str = "info"
            message: str = ""

        def detect_being_ignored(*args, **kwargs): return []
        def detect_failures(*args, **kwargs): return []
        def detect_overfitting(*args, **kwargs): return []
        def detect_playing_safe(*args, **kwargs): return []
        def detect_regression_to_mean(*args, **kwargs): return []
        def format_alerts(*args, **kwargs): return ""
