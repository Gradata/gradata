"""Backward-compat shim. Tries gradata_cloud first, then enhancements, then stubs."""
from dataclasses import dataclass, field

try:
    from gradata_cloud.graduation.pattern_extractor import (
        ExtractedPattern,
        extract_patterns,
        merge_patterns,
        patterns_to_lessons,
    )
except ImportError:
    try:
        from gradata.enhancements.pattern_extractor import (
            ExtractedPattern,
            extract_patterns,
            merge_patterns,
            patterns_to_lessons,
        )
    except ImportError:
        @dataclass
        class ExtractedPattern:  # type: ignore[no-redef]
            category: str = ""
            description: str = ""
            confidence: float = 0.0
            edits: list = field(default_factory=list)

        def extract_patterns(*args, **kwargs):
            return []

        def merge_patterns(*args, **kwargs):
            return []

        def patterns_to_lessons(*args, **kwargs):
            return []
