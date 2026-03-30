"""Brain mixin — Pipeline and Task Type registration methods."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class BrainPipelineMixin:
    """Pipeline creation and task type registration for Brain."""

    # ── Pipeline ──────────────────────────────────────────────────────

    def pipeline(self, *stages) -> "Pipeline":
        """Create a Pipeline with the given Stage instances."""
        from gradata.patterns.pipeline import Pipeline
        return Pipeline(*stages)

    def register_task_type(
        self,
        name: str,
        keywords: list[str],
        domain_hint: str = "",
        *,
        prepend: bool = False,
    ) -> None:
        """Register a custom task type in the global scope classifier."""
        from gradata.patterns.scope import register_task_type as _register
        _register(name, keywords, domain_hint, prepend=prepend)
