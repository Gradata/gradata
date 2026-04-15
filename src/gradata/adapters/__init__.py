"""
External memory adapters for Gradata.
======================================

Opt-in integrations that let Gradata mirror corrections and pull relevant
context from external memory backends (Mem0, Letta, EverMind, Hermes, ...).

Adapters are **not** wired into Gradata's event pipeline automatically.
Users call adapter methods themselves from their own `Brain.correct()`
callsites. A future release may add a `Brain(...)` constructor option
that auto-mirrors events to an adapter.

All adapters implement the :class:`MemoryAdapter` protocol
(:mod:`gradata.adapters.base`).
"""

from __future__ import annotations

from gradata.adapters.base import MemoryAdapter
from gradata.adapters.mem0 import Mem0Adapter

__all__ = ["Mem0Adapter", "MemoryAdapter"]
