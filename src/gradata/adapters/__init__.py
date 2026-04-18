"""
External memory adapters for Gradata.
======================================

Opt-in integrations that let Gradata mirror corrections and pull relevant
context from external memory backends (Mem0, Letta, EverMind, Hermes, ...).

Adapters are **not** wired into Gradata's event pipeline automatically.
Users call adapter methods themselves from their own `Brain.correct()`
callsites. A future release may add a `Brain(...)` constructor option
that auto-mirrors events to an adapter.

All adapters implement the :class:`MemoryAdapter` protocol defined below.
Every adapter must be safe to call from any thread and must never raise
on transport failure. A failed call returns ``None`` (for writes) or
``[]`` (for reads) and logs at ``WARNING``.
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
