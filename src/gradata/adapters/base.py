"""
MemoryAdapter protocol — backend-agnostic shape for external memory stores.
===========================================================================

Every external adapter (Mem0, Letta, EverMind, Hermes, ...) implements this
same three-method protocol so callers can swap backends without touching
their learning code.

Design notes:
- `typing.runtime_checkable` so callers can do `isinstance(x, MemoryAdapter)`
- Sync-only for now; an async counterpart can ship later once a concrete
  adapter needs it.
- Adapters NEVER raise on backend failure. They log and return `None` or
  `[]` so a misbehaving memory backend cannot take down the host brain.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class MemoryAdapter(Protocol):
    """Backend-agnostic interface for mirroring corrections to / pulling
    context from an external memory store.

    Concrete implementations must be safe to call from any thread and must
    never raise on transport failure. A failed call returns ``None`` (for
    writes) or ``[]`` (for reads) and logs at ``WARNING``.
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

        Args:
            draft: What the AI originally produced.
            final: What the user corrected it to.
            summary: Short human-readable summary of the correction.
            tags: Optional tags / categories for filtering on retrieval.
            metadata: Optional extra metadata (session id, lesson id, etc).

        Returns:
            The external memory id (string) on success, or ``None`` on
            failure. MUST NOT raise.
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

        Args:
            query: Free-text query (usually the current draft or task).
            k: Max number of memories to return.
            filters: Optional backend-specific filters (user_id, tags, ...).

        Returns:
            A list of dicts with keys ``text``, ``metadata``, ``score``.
            Returns ``[]`` on failure. MUST NOT raise.
        """
        ...

    def reconcile(
        self,
        *,
        gradata_memory_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Return a diff between Gradata's local memory and the external
        backend.

        Implementations may be best-effort. The return shape is
        intentionally loose (a dict with keys like ``only_local``,
        ``only_remote``, ``conflicts``) so different backends can report
        whatever their API actually supports.

        Returns:
            A reconciliation report dict. Returns ``{}`` on failure.
            MUST NOT raise.
        """
        ...
