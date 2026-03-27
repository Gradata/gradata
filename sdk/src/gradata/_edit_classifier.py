"""Backward-compat shim. Tries gradata_cloud first, then enhancements, then stubs."""
from dataclasses import dataclass

try:
    from gradata_cloud.graduation.edit_classifier import (  # noqa: F401
        EditClassification, classify_edits, summarize_edits,
    )
except ImportError:
    try:
        from gradata.enhancements.edit_classifier import (  # noqa: F401
            EditClassification, classify_edits, summarize_edits,
        )
    except ImportError:
        @dataclass
        class EditClassification:  # type: ignore[no-redef]
            category: str = "unknown"
            confidence: float = 0.0
            description: str = ""

        def classify_edits(*args, **kwargs):
            return []

        def summarize_edits(*args, **kwargs):
            return ""
