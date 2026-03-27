"""Backward-compat shim. Tries gradata_cloud first, then enhancements, then stubs."""
from dataclasses import dataclass, field

try:
    from gradata_cloud.scoring.metrics import (  # noqa: F401
        MetricsWindow, compute_blandness, compute_metrics, format_metrics,
    )
except ImportError:
    try:
        from gradata.enhancements.metrics import (  # noqa: F401
            MetricsWindow, compute_blandness, compute_metrics, format_metrics,
        )
    except ImportError:
        @dataclass
        class MetricsWindow:  # type: ignore[no-redef]
            sessions: list = field(default_factory=list)
            window_size: int = 10

        def compute_blandness(*args, **kwargs): return 0.0
        def compute_metrics(*args, **kwargs): return {}
        def format_metrics(*args, **kwargs): return ""
