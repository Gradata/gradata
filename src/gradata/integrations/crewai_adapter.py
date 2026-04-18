"""CrewAI Integration — DEPRECATED.

.. deprecated::
    ``gradata.integrations.crewai_adapter`` is deprecated and will be
    removed in v0.8.0.

    For output enforcement (recommended)::

        from ..middleware import CrewAIGuard
        agent = Agent(role="Writer", guardrails=[CrewAIGuard(brain_path="./brain")])

    :class:`~gradata.middleware.crewai_adapter.CrewAIGuard` enforces RULE-tier
    patterns on agent outputs.  :class:`BrainCrewMemory` (this module) provides
    persistent memory storage — both can coexist.  Migrate to the guard for
    rule enforcement; a retrieval-memory equivalent for CrewAI is planned for
    gradata.middleware before v0.8.0.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "gradata.integrations.crewai_adapter is deprecated and will be removed "
    "in v0.8.0.  Use 'from gradata.middleware import CrewAIGuard' for rule "
    "enforcement, or keep BrainCrewMemory here until a memory equivalent "
    "lands in gradata.middleware.",
    DeprecationWarning,
    stacklevel=2,
)

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger("gradata.integrations.crewai")


class BrainCrewMemory:
    """CrewAI-compatible memory backed by Gradata.

    .. deprecated::
        This class will be removed in v0.8.0.  Use
        :class:`gradata.middleware.CrewAIGuard` for rule enforcement.
    """

    def __init__(self, brain_dir: str | Path = "./brain") -> None:
        from ..brain import Brain

        self.brain = Brain(brain_dir)

    def save(self, value: str, metadata: dict | None = None, agent: str = "") -> None:
        try:
            if hasattr(self.brain, "observe"):
                self.brain.observe(
                    [{"role": "assistant", "content": value}],
                    user_id=agent or "default",
                )
        except Exception as e:
            logger.debug("CrewAI memory save skipped: %s", e)

    def search(self, query: str, limit: int = 5) -> list[dict]:
        try:
            results = self.brain.search(query, top_k=limit)
            return [
                {
                    "content": r.get("text", ""),
                    "score": r.get("score", 0),
                    "source": r.get("source", ""),
                }
                for r in results
            ]
        except Exception:
            return []

    def reset(self) -> None:
        """No-op for persistent brain memory."""

    def get_rules(self, task: str = "", context: dict | None = None) -> str:
        try:
            return self.brain.apply_brain_rules(task, context)
        except Exception:
            return ""
