"""External memory adapters — opt-in integrations mirroring corrections and
retrieving context from Mem0/Letta/EverMind/etc. Not auto-wired; users call
from their own ``Brain.correct()`` sites. All adapters implement
:class:`MemoryAdapter`, thread-safe, never raise on transport failure.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class MemoryAdapter(Protocol):
    """Backend-agnostic interface for mirroring corrections to / pulling
    context from an external memory store.
    """

    def push_correction(
        self,
        *,
        draft: str,
        final: str,
        summary: str = "",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """Mirror a Gradata correction to the external store.

        Returns the external memory id on success, or ``None`` on failure.
        MUST NOT raise.
        """
        ...

    def pull_memory_for_context(
        self,
        query: str,
        *,
        k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch up to ``k`` memories relevant to ``query``.

        Returns a list of dicts with keys ``text``, ``metadata``, ``score``.
        Returns ``[]`` on failure. MUST NOT raise.
        """
        ...

    def reconcile(
        self,
        *,
        gradata_memory_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Return a diff between Gradata's local memory and the external backend.

        Return shape is intentionally loose. Returns ``{}`` on failure.
        MUST NOT raise.
        """
        ...


from .mem0 import Mem0Adapter

__all__ = ["Mem0Adapter", "MemoryAdapter"]
