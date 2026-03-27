"""
Persistent Memory Pattern
==========================
SDK abstraction over the brain's storage layer (events.jsonl, prospects/,
sessions/, PATTERNS.md).

Three memory types model how humans and agents retain knowledge:

    Episodic   — what happened (interactions, outcomes, session lessons)
    Semantic   — what is true (entity facts, domain knowledge)
    Procedural — how to do things (workflows, effective patterns)

Each type has a focused class with lifecycle methods, all coordinated
through :class:`MemoryManager`.  The :class:`InMemoryStore` dict-based
backend is provided for testing and small/embedded brains; production
brains swap in a SQLite or vector-backed store by implementing
:class:`MemoryStore`.

Lifecycle
---------
    1. ``store()`` — creates Memory with reinforcement_count=0
    2. ``retrieve()`` — bumps last_accessed on every match
    3. ``reinforce()`` (ProceduralMemory) — increments reinforcement_count
    4. ``decay()`` — prunes memories older than max_age_days that have
       fewer than min_reinforcements surviving reinforcements
    5. ``conflict_resolve()`` — keep newer, merge metadata fields

Usage example::

    from gradata.patterns.memory import MemoryManager

    mm = MemoryManager()                          # InMemoryStore by default

    mid = mm.store("episodic", "User corrected email tone — too casual")
    mm.store("semantic",   "Acme Corp budget: $500K/yr AI tooling")
    mm.store("procedural", "Always validate data before processing")

    hits = mm.retrieve("email tone")
    print(hits[0].content)                        # User corrected email tone ...

    pruned = mm.decay(max_age_days=30, min_reinforcements=1)
    print(mm.stats())
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    pass  # reserved for future type-only imports


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_TYPES: frozenset[str] = frozenset({
    "episodic",     # What happened (interactions, outcomes, session lessons)
    "semantic",     # What is true (entity facts, domain knowledge)
    "procedural",   # How to do things (workflows, effective patterns)
    "prospective",  # What to do in the future (follow-ups, scheduled actions)
    # Cognitive science basis: Frontiers in Cognition (2024), "Expanded
    # Taxonomies of Human Memory." Prospective memory = remembering to
    # perform intended actions. Critical for sales (follow-up cadences),
    # project management (deadlines), and any agent workflow with deferred tasks.
})

_ISO_FORMAT = "%Y-%m-%dT%H:%M:%S.%f+00:00"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Return current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(ts: str) -> datetime:
    """Parse an ISO 8601 timestamp (with or without microseconds / 'Z' suffix).

    Args:
        ts: ISO 8601 string, e.g. ``"2026-03-24T12:00:00+00:00"`` or
            ``"2026-03-24T12:00:00.123456+00:00"`` or ``"...Z"``.

    Returns:
        Timezone-aware :class:`datetime` in UTC.

    Raises:
        ValueError: If ``ts`` cannot be parsed.
    """
    # Normalise the trailing 'Z' that Python's fromisoformat() rejects before 3.11
    normalised = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(normalised)


# ---------------------------------------------------------------------------
# Core data class
# ---------------------------------------------------------------------------


@dataclass
class Memory:
    """A single unit of brain memory.

    Attributes:
        id: Unique identifier (UUID4 string).
        memory_type: One of ``"episodic"``, ``"semantic"``, or
            ``"procedural"``.
        content: Human-readable memory text.
        metadata: Arbitrary key/value bag — source, entity, confidence, etc.
        created: ISO 8601 UTC timestamp of creation.
        last_accessed: ISO 8601 UTC timestamp of most recent retrieval.
        reinforcement_count: How many times this memory has been explicitly
            reinforced (used/confirmed).  Newly created memories start at 0.
    """

    id: str
    memory_type: str
    content: str
    metadata: dict
    created: str
    last_accessed: str
    reinforcement_count: int = 0

    def __post_init__(self) -> None:
        if self.memory_type not in VALID_TYPES:
            raise ValueError(
                f"Invalid memory_type {self.memory_type!r}. "
                f"Must be one of: {sorted(VALID_TYPES)}"
            )
        if not self.content:
            raise ValueError("Memory content must not be empty.")

    def age_days(self) -> float:
        """Return age in fractional days since creation (UTC).

        Returns:
            Non-negative float representing elapsed days.
        """
        created_dt = _parse_iso(self.created)
        delta = datetime.now(timezone.utc) - created_dt
        return delta.total_seconds() / 86_400


# ---------------------------------------------------------------------------
# MemoryStore protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class MemoryStore(Protocol):
    """Backend-agnostic interface for memory persistence.

    Any object satisfying this structural protocol can be passed to
    :class:`MemoryManager` as a custom storage backend.

    All methods are synchronous; wrap with an executor for async runtimes.
    """

    def store(self, memory: Memory) -> str:
        """Persist a memory and return its id.

        Args:
            memory: Fully constructed :class:`Memory` to persist.

        Returns:
            The ``memory.id`` string (for caller convenience).
        """
        ...

    def retrieve(
        self,
        query: str,
        types: list[str] | None = None,
        limit: int = 10,
    ) -> list[Memory]:
        """Retrieve memories matching ``query``.

        Args:
            query: Substring / keyword to match against ``Memory.content``.
            types: If provided, only memories with ``memory_type`` in this
                list are considered.  ``None`` means all types.
            limit: Maximum number of results to return.

        Returns:
            List of matching :class:`Memory` objects, most recently accessed
            first.
        """
        ...

    def update(self, memory_id: str, content: str) -> None:
        """Replace the content of an existing memory in place.

        Args:
            memory_id: ``Memory.id`` of the record to update.
            content: New content string.

        Raises:
            KeyError: If ``memory_id`` does not exist.
        """
        ...

    def delete(self, memory_id: str) -> None:
        """Remove a memory permanently.

        Args:
            memory_id: ``Memory.id`` of the record to remove.

        Raises:
            KeyError: If ``memory_id`` does not exist.
        """
        ...


# ---------------------------------------------------------------------------
# InMemoryStore — dict-based reference implementation
# ---------------------------------------------------------------------------


class InMemoryStore:
    """Dictionary-backed :class:`MemoryStore` for testing and small brains.

    All data lives in a plain ``dict[str, Memory]`` — no external
    dependencies required.  Retrieval uses case-insensitive substring
    matching on ``Memory.content``.

    This class satisfies the :class:`MemoryStore` structural protocol; no
    inheritance required.

    Args:
        initial: Optional pre-populated mapping of ``{id: Memory}``.  Useful
            for constructing stores from serialised data.

    Example::

        store = InMemoryStore()
        mid = store.store(Memory(id=str(uuid.uuid4()), ...))
        results = store.retrieve("budget", types=["semantic"])
    """

    def __init__(self, initial: dict[str, Memory] | None = None) -> None:
        self._data: dict[str, Memory] = dict(initial) if initial else {}

    # -- MemoryStore interface -----------------------------------------------

    def store(self, memory: Memory) -> str:
        """Persist ``memory`` and return its ``id``.

        Args:
            memory: :class:`Memory` instance to store.

        Returns:
            ``memory.id`` string.
        """
        self._data[memory.id] = memory
        return memory.id

    def retrieve(
        self,
        query: str,
        types: list[str] | None = None,
        limit: int = 10,
    ) -> list[Memory]:
        """Return memories whose content contains ``query`` (case-insensitive).

        Matching memories have their ``last_accessed`` field updated before
        being returned.  Results are ordered by ``last_accessed`` descending
        (most recent first).

        Args:
            query: Substring to search for inside ``Memory.content``.
            types: Restrict to these memory types.  ``None`` means all types.
            limit: Maximum number of results.

        Returns:
            Matching :class:`Memory` objects, most recently accessed first.
        """
        query_lower = query.lower()
        allowed = set(types) if types is not None else VALID_TYPES
        now = _now_iso()

        matches: list[Memory] = []
        for memory in self._data.values():
            if memory.memory_type not in allowed:
                continue
            if query_lower in memory.content.lower():
                memory.last_accessed = now
                matches.append(memory)

        matches.sort(key=lambda m: m.last_accessed, reverse=True)
        return matches[:limit]

    def update(self, memory_id: str, content: str) -> None:
        """Replace content of an existing memory.

        Args:
            memory_id: Target memory id.
            content: Replacement content string.

        Raises:
            KeyError: If ``memory_id`` not found.
            ValueError: If ``content`` is empty.
        """
        if memory_id not in self._data:
            raise KeyError(f"Memory not found: {memory_id!r}")
        if not content:
            raise ValueError("Memory content must not be empty.")
        self._data[memory_id].content = content

    def delete(self, memory_id: str) -> None:
        """Remove a memory from the store.

        Args:
            memory_id: Target memory id.

        Raises:
            KeyError: If ``memory_id`` not found.
        """
        if memory_id not in self._data:
            raise KeyError(f"Memory not found: {memory_id!r}")
        del self._data[memory_id]

    # -- Extras (not part of the protocol, but useful) -----------------------

    def all(self) -> list[Memory]:
        """Return all stored memories (unordered).

        Returns:
            Snapshot list of every :class:`Memory` in the store.
        """
        return list(self._data.values())

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return f"InMemoryStore({len(self._data)} memories)"


# ---------------------------------------------------------------------------
# EpisodicMemory — what happened
# ---------------------------------------------------------------------------


class EpisodicMemory:
    """Episodic memory layer — records of events, interactions, and outcomes.

    Episodic memories are time-stamped accounts of things that occurred:
    session events, corrections, outcomes, and lessons learned.  They decay
    naturally over time when not reinforced, reflecting the biological
    metaphor of fading episodic recall.

    Args:
        store: :class:`MemoryStore` backend.  Defaults to a fresh
            :class:`InMemoryStore` if not provided.

    Example::

        ep = EpisodicMemory()
        mid = ep.store("Sent follow-up to Hassan Ali after demo")
        results = ep.retrieve("Hassan Ali")
    """

    memory_type: str = "episodic"

    def __init__(self, store: MemoryStore | None = None) -> None:
        self._store: MemoryStore = store if store is not None else InMemoryStore()

    def store(
        self,
        content: str,
        metadata: dict | None = None,
        *,
        source: str = "agent",
    ) -> str:
        """Record an episodic event.

        Args:
            content: Description of what happened.
            metadata: Optional extra context (entity, outcome, confidence).
            source: Origin tag (e.g. ``"session"``, ``"correction"``).

        Returns:
            Memory id string.
        """
        now = _now_iso()
        meta: dict = {"source": source}
        if metadata:
            meta.update(metadata)

        memory = Memory(
            id=str(uuid.uuid4()),
            memory_type=self.memory_type,
            content=content,
            metadata=meta,
            created=now,
            last_accessed=now,
        )
        return self._store.store(memory)

    def retrieve(self, query: str, limit: int = 10) -> list[Memory]:
        """Retrieve episodic memories matching ``query``.

        Args:
            query: Keyword / substring to search for.
            limit: Maximum number of results.

        Returns:
            Matching :class:`Memory` objects, most recently accessed first.
        """
        return self._store.retrieve(query, types=[self.memory_type], limit=limit)

    def decay(self, max_age_days: int = 30, min_reinforcements: int = 1) -> list[str]:
        """Remove stale, unreinforced episodic memories.

        A memory is pruned when both conditions hold:

        - Age in days exceeds ``max_age_days``.
        - ``reinforcement_count < min_reinforcements``.

        Args:
            max_age_days: Age threshold in days.
            min_reinforcements: Minimum reinforcements to survive pruning.

        Returns:
            List of pruned memory ids.
        """
        if not isinstance(self._store, InMemoryStore):
            raise NotImplementedError(
                "decay() is only implemented for InMemoryStore. "
                "Custom backends must implement their own pruning logic."
            )
        pruned: list[str] = []
        for memory in list(self._store.all()):
            if memory.memory_type != self.memory_type:
                continue
            if (
                memory.age_days() > max_age_days
                and memory.reinforcement_count < min_reinforcements
            ):
                self._store.delete(memory.id)
                pruned.append(memory.id)
        return pruned


# ---------------------------------------------------------------------------
# SemanticMemory — what is true
# ---------------------------------------------------------------------------


class SemanticMemory:
    """Semantic memory layer — facts, domain knowledge, and entity attributes.

    Semantic memories represent standing truths: prospect attributes,
    company facts, domain rules, and any knowledge that persists across
    episodes.  Conflict resolution keeps the newer memory and merges
    metadata from both.

    Args:
        store: :class:`MemoryStore` backend.  Defaults to a fresh
            :class:`InMemoryStore` if not provided.

    Example::

        sm = SemanticMemory()
        mid = sm.store("Acme Corp budget: $500K/yr AI tooling",
                       metadata={"entity": "Acme Corp", "confidence": 0.9})
        sm.update(mid, "Acme Corp budget: $600K/yr AI tooling (revised Q2)")
        resolved = sm.conflict_resolve(memory_a, memory_b)
    """

    memory_type: str = "semantic"

    def __init__(self, store: MemoryStore | None = None) -> None:
        self._store: MemoryStore = store if store is not None else InMemoryStore()

    def store(
        self,
        content: str,
        metadata: dict | None = None,
        *,
        source: str = "agent",
    ) -> str:
        """Record a semantic fact.

        Args:
            content: The fact or piece of domain knowledge.
            metadata: Optional context (entity, confidence, source).
            source: Origin tag.

        Returns:
            Memory id string.
        """
        now = _now_iso()
        meta: dict = {"source": source}
        if metadata:
            meta.update(metadata)

        memory = Memory(
            id=str(uuid.uuid4()),
            memory_type=self.memory_type,
            content=content,
            metadata=meta,
            created=now,
            last_accessed=now,
        )
        return self._store.store(memory)

    def retrieve(self, query: str, limit: int = 10) -> list[Memory]:
        """Retrieve semantic facts matching ``query``.

        Args:
            query: Keyword / substring to search for.
            limit: Maximum number of results.

        Returns:
            Matching :class:`Memory` objects, most recently accessed first.
        """
        return self._store.retrieve(query, types=[self.memory_type], limit=limit)

    def update(self, memory_id: str, content: str) -> None:
        """Revise an existing semantic fact in place.

        Args:
            memory_id: Target memory id.
            content: Updated fact text.

        Raises:
            KeyError: If ``memory_id`` not found.
        """
        self._store.update(memory_id, content)

    def conflict_resolve(self, memory_a: Memory, memory_b: Memory) -> Memory:
        """Resolve a conflict between two semantic memories for the same fact.

        Strategy:

        - Keep the **newer** memory (by ``created`` timestamp).
        - Merge ``metadata`` from the older memory into the winner, with
          the winner's keys taking precedence on collision.
        - The winner's ``reinforcement_count`` is incremented by 1 to signal
          it survived a conflict.

        Args:
            memory_a: First candidate memory.
            memory_b: Second candidate memory.

        Returns:
            The resolved :class:`Memory` (winner with merged metadata).
        """
        dt_a = _parse_iso(memory_a.created)
        dt_b = _parse_iso(memory_b.created)

        winner, loser = (memory_a, memory_b) if dt_a >= dt_b else (memory_b, memory_a)

        # Merge loser's metadata under winner's (winner takes precedence)
        merged_meta = {**loser.metadata, **winner.metadata}
        winner.metadata = merged_meta
        winner.reinforcement_count += 1

        return winner


# ---------------------------------------------------------------------------
# ProceduralMemory — how to do things
# ---------------------------------------------------------------------------


class ProceduralMemory:
    """Procedural memory layer — workflows, patterns, and effective techniques.

    Procedural memories encode *how* to do things: multi-step processes,
    patterns that work, heuristics derived from experience.  They strengthen
    through reinforcement (repeated successful application) and weaken
    through disuse.

    Args:
        store: :class:`MemoryStore` backend.  Defaults to a fresh
            :class:`InMemoryStore` if not provided.

    Example::

        pm = ProceduralMemory()
        mid = pm.store("Always enrich leads before tiering — never tier on headline alone")
        pm.reinforce(mid)          # confirmed effective again
        results = pm.retrieve("enrichment")
    """

    memory_type: str = "procedural"

    def __init__(self, store: MemoryStore | None = None) -> None:
        self._store: MemoryStore = store if store is not None else InMemoryStore()

    def store(
        self,
        content: str,
        metadata: dict | None = None,
        *,
        source: str = "agent",
    ) -> str:
        """Record a procedural pattern or workflow.

        Args:
            content: Description of the procedure / pattern.
            metadata: Optional context (domain, confidence, trigger).
            source: Origin tag.

        Returns:
            Memory id string.
        """
        now = _now_iso()
        meta: dict = {"source": source}
        if metadata:
            meta.update(metadata)

        memory = Memory(
            id=str(uuid.uuid4()),
            memory_type=self.memory_type,
            content=content,
            metadata=meta,
            created=now,
            last_accessed=now,
        )
        return self._store.store(memory)

    def retrieve(self, query: str, limit: int = 10) -> list[Memory]:
        """Retrieve procedural patterns matching ``query``.

        Args:
            query: Keyword / substring to search for.
            limit: Maximum number of results.

        Returns:
            Matching :class:`Memory` objects, most recently accessed first.
        """
        return self._store.retrieve(query, types=[self.memory_type], limit=limit)

    def reinforce(self, memory_id: str) -> int:
        """Increment the reinforcement count for a procedural memory.

        Called when the procedure is confirmed effective — its
        ``reinforcement_count`` grows, making it more durable against
        :meth:`MemoryManager.decay`.

        Args:
            memory_id: Target memory id.

        Returns:
            Updated ``reinforcement_count`` value.

        Raises:
            KeyError: If ``memory_id`` not found in the store.
            TypeError: If the backing store is not an :class:`InMemoryStore`
                (custom backends must implement their own reinforcement).
        """
        if not isinstance(self._store, InMemoryStore):
            raise NotImplementedError(
                "reinforce() is only implemented for InMemoryStore. "
                "Custom backends must handle reinforcement themselves."
            )
        # Access internal dict directly — safe because we type-checked above
        memory = self._store._data.get(memory_id)
        if memory is None:
            raise KeyError(f"Memory not found: {memory_id!r}")
        memory.reinforcement_count += 1
        return memory.reinforcement_count

    def decay(self, max_age_days: int = 30, min_reinforcements: int = 1) -> list[str]:
        """Remove stale, unreinforced procedural patterns.

        Args:
            max_age_days: Age threshold in days.
            min_reinforcements: Minimum reinforcements to survive pruning.

        Returns:
            List of pruned memory ids.
        """
        if not isinstance(self._store, InMemoryStore):
            raise NotImplementedError(
                "decay() is only implemented for InMemoryStore. "
                "Custom backends must implement their own pruning logic."
            )
        pruned: list[str] = []
        for memory in list(self._store.all()):
            if memory.memory_type != self.memory_type:
                continue
            if (
                memory.age_days() > max_age_days
                and memory.reinforcement_count < min_reinforcements
            ):
                self._store.delete(memory.id)
                pruned.append(memory.id)
        return pruned


# ---------------------------------------------------------------------------
# MemoryManager — unified interface
# ---------------------------------------------------------------------------


class MemoryManager:
    """Unified interface across all three memory types.

    :class:`MemoryManager` is the top-level entry point for SDK consumers.
    It owns a single :class:`MemoryStore` shared across all three typed
    sub-managers, so a single ``retrieve()`` call can span all types.

    Args:
        store: Optional custom :class:`MemoryStore` backend.  When not
            provided, a fresh :class:`InMemoryStore` is used — suitable for
            unit tests and small brains without a persistence requirement.

    Example::

        mm = MemoryManager()                    # in-memory, zero config

        mid1 = mm.store("episodic", "Sent email to Jane Doe")
        mid2 = mm.store("semantic", "Acme Corp budget: $500K")
        mid3 = mm.store("procedural", "Always enrich before tiering")

        all_hits = mm.retrieve("Acme")          # cross-type search
        ep_hits  = mm.retrieve("email", types=["episodic"])

        mm.update(mid2, "Acme Corp budget: $600K (revised)")

        pruned_ids = mm.decay(max_age_days=30, min_reinforcements=1)
        print(mm.stats())
    """

    def __init__(self, store: MemoryStore | None = None) -> None:
        self._store: MemoryStore = store if store is not None else InMemoryStore()

        # Typed sub-managers share the same backing store
        self.episodic: EpisodicMemory = EpisodicMemory(self._store)
        self.semantic: SemanticMemory = SemanticMemory(self._store)
        self.procedural: ProceduralMemory = ProceduralMemory(self._store)

    # -- Core operations -----------------------------------------------------

    def store(
        self,
        memory_type: str,
        content: str,
        metadata: dict | None = None,
    ) -> str:
        """Store a memory of the given type.

        Args:
            memory_type: One of ``"episodic"``, ``"semantic"``,
                ``"procedural"``.
            content: Memory text.
            metadata: Optional key/value context bag.

        Returns:
            Memory id string.

        Raises:
            ValueError: If ``memory_type`` is not recognised.
        """
        if memory_type == "episodic":
            return self.episodic.store(content, metadata)
        if memory_type == "semantic":
            return self.semantic.store(content, metadata)
        if memory_type == "procedural":
            return self.procedural.store(content, metadata)
        raise ValueError(
            f"Unknown memory_type {memory_type!r}. "
            f"Valid types: {sorted(VALID_TYPES)}"
        )

    def retrieve(
        self,
        query: str,
        types: list[str] | None = None,
        limit: int = 10,
    ) -> list[Memory]:
        """Retrieve memories matching ``query``, optionally filtered by type.

        Delegates to the backing store for a unified cross-type search.
        Each matched memory has its ``last_accessed`` timestamp refreshed.

        Args:
            query: Substring to search for in ``Memory.content``.
            types: Restrict to these types.  ``None`` searches all types.
            limit: Maximum number of results.

        Returns:
            Matching :class:`Memory` objects, most recently accessed first.
        """
        return self._store.retrieve(query, types=types, limit=limit)

    def update(self, memory_id: str, content: str) -> None:
        """Replace the content of a memory, regardless of type.

        Args:
            memory_id: Target memory id.
            content: New content string.

        Raises:
            KeyError: If ``memory_id`` not found.
        """
        self._store.update(memory_id, content)

    # -- Lifecycle -----------------------------------------------------------

    def decay(
        self,
        max_age_days: int = 30,
        min_reinforcements: int = 1,
    ) -> list[str]:
        """Prune memories that are both old and unreinforced.

        A memory is removed when:

        - Its age exceeds ``max_age_days``, **AND**
        - Its ``reinforcement_count < min_reinforcements``.

        Operates directly on the backing store.  Only supported for
        :class:`InMemoryStore`; custom backends must prune themselves.

        Args:
            max_age_days: Age threshold in days (default: 30).
            min_reinforcements: Minimum count to be considered reinforced
                (default: 1).

        Returns:
            List of pruned memory ids.

        Raises:
            NotImplementedError: If the backing store is not an
                :class:`InMemoryStore`.
        """
        if not isinstance(self._store, InMemoryStore):
            raise NotImplementedError(
                "decay() is only implemented for InMemoryStore. "
                "Custom backends must implement their own pruning logic."
            )
        pruned: list[str] = []
        for memory in list(self._store.all()):
            if (
                memory.age_days() > max_age_days
                and memory.reinforcement_count < min_reinforcements
            ):
                self._store.delete(memory.id)
                pruned.append(memory.id)
        return pruned

    def conflict_resolve(self, memory_a: Memory, memory_b: Memory) -> Memory:
        """Resolve a conflict between two memories for the same fact.

        Delegates to :meth:`SemanticMemory.conflict_resolve`.  Keeps the
        newer memory, merges metadata, and increments the winner's
        reinforcement count.

        Args:
            memory_a: First candidate memory.
            memory_b: Second candidate memory.

        Returns:
            The winning (newer) :class:`Memory` with merged metadata.
        """
        return self.semantic.conflict_resolve(memory_a, memory_b)

    # -- Introspection -------------------------------------------------------

    def stats(self) -> dict:
        """Return a summary of current memory state.

        Only supported for :class:`InMemoryStore`; custom backends should
        override or extend :class:`MemoryManager` to provide their own
        statistics.

        Returns:
            Dict with keys:

            - ``total``: total memory count.
            - ``by_type``: mapping of ``{memory_type: count}``.
            - ``avg_reinforcements``: mean ``reinforcement_count`` across all
              memories (float, rounded to 2 dp).
            - ``oldest_created``: ISO timestamp of oldest memory, or ``None``
              if the store is empty.
            - ``newest_created``: ISO timestamp of newest memory, or ``None``
              if the store is empty.

        Raises:
            NotImplementedError: If the backing store is not an
                :class:`InMemoryStore`.
        """
        if not isinstance(self._store, InMemoryStore):
            raise NotImplementedError(
                "stats() is only implemented for InMemoryStore. "
                "Custom backends must implement their own statistics."
            )
        all_memories = self._store.all()
        total = len(all_memories)

        by_type: dict[str, int] = {t: 0 for t in sorted(VALID_TYPES)}
        for m in all_memories:
            by_type[m.memory_type] = by_type.get(m.memory_type, 0) + 1

        avg_reinforcements = (
            round(sum(m.reinforcement_count for m in all_memories) / total, 2)
            if total > 0
            else 0.0
        )

        created_timestamps = [m.created for m in all_memories]
        oldest = min(created_timestamps) if created_timestamps else None
        newest = max(created_timestamps) if created_timestamps else None

        return {
            "total": total,
            "by_type": by_type,
            "avg_reinforcements": avg_reinforcements,
            "oldest_created": oldest,
            "newest_created": newest,
        }

    def __repr__(self) -> str:
        try:
            count = len(self._store) if hasattr(self._store, "__len__") else "?"
        except Exception:
            count = "?"
        return f"MemoryManager(store={self._store.__class__.__name__}, memories={count})"


# ---------------------------------------------------------------------------
# Memory Scope Classification (extracted from brain/scripts/memory_scope.py)
# ---------------------------------------------------------------------------
# Three-scope classification for SDK marketplace portability.
# PROJECT = shareable industry patterns, LOCAL = deployment-specific,
# USER = personal data (never shared in marketplace).
#
# Pure computation: no file I/O, no SQLite. The brain-layer script
# (brain/scripts/memory_scope.py) uses these functions for actual scanning.

import re as _re
from pathlib import Path as _Path

MEMORY_SCOPES: tuple[str, ...] = ("project", "local", "user")

# Path classification rules. Order matters: first match wins.
# Paths are relative to the brain directory.
_SCOPE_PATH_RULES: list[tuple[str, str]] = [
    # PROJECT scope (shareable patterns)
    (r"^emails/PATTERNS\.md$", "project"),
    (r"^personas/", "project"),
    (r"^objections/", "project"),
    (r"^competitors/", "project"),
    (r"^icp-research", "project"),
    (r"^learnings/", "project"),

    # USER scope (personal, never shared)
    (r"^metrics/", "user"),
    (r"^loop-state\.md$", "user"),
    (r"^system-patterns\.md$", "user"),
    (r"^self-model\.md$", "user"),
    (r"^audits/", "user"),
    (r"^evals/", "user"),

    # LOCAL scope (deployment-specific)
    (r"^prospects/", "local"),
    (r"^pipeline/", "local"),
    (r"^demos/", "local"),
    (r"^messages/", "local"),
    (r"^sessions/", "local"),
    (r"^forecasting\.md$", "local"),
    (r"^signals\.md$", "local"),
    (r"^emails/", "local"),
    (r"^templates/", "local"),
    (r"^cache/", "local"),
    (r"^snapshots/", "local"),
    (r"^vault/", "local"),
    (r"^exports/", "local"),
    (r"^logs/", "local"),
    (r"^backups/", "local"),
]

_SCOPE_PATH_RULES_COMPILED = [(_re.compile(pat), scope) for pat, scope in _SCOPE_PATH_RULES]

# Event type classification
_SCOPE_EVENT_TYPES: dict[str, str] = {
    # USER scope
    "CORRECTION": "user",
    "CALIBRATION": "user",
    "COST_EVENT": "user",
    "AUDIT_SCORE": "user",
    "HALLUCINATION": "user",
    # LOCAL scope
    "DELTA_TAG": "local",
    "OUTPUT": "local",
    "GATE_RESULT": "local",
    "HEALTH_CHECK": "local",
    "TOOL_FAILURE": "local",
    "DEFER": "local",
    "STEP_COMPLETE": "local",
    "STALE_DATA": "local",
    "GATE_OVERRIDE": "local",
    "LESSON_CHANGE": "local",
}

# Tag prefix classification
_SCOPE_TAG_PREFIXES: dict[str, str] = {
    "prospect:": "local",
    "system:": "local",
    "output:": "user",
    "gate:": "local",
    "pattern:": "project",
}


def classify_memory_scope(
    source_path: str | None = None,
    brain_dir: str | None = None,
    event_type: str | None = None,
    tags: list[str] | None = None,
) -> str:
    """Auto-classify what scope a piece of brain data belongs to.

    Priority: path > event_type > tags > default (local).

    Pure function: no file I/O.

    Args:
        source_path: File path (absolute or relative to brain_dir).
        brain_dir: Brain directory root (for computing relative paths).
        event_type: Event type string (CORRECTION, GATE_RESULT, etc.)
        tags: List of tag strings.

    Returns:
        "project", "local", or "user"
    """
    # 1. Path-based classification
    if source_path:
        p = _Path(source_path)
        if brain_dir:
            try:
                rel = p.relative_to(brain_dir)
            except ValueError:
                rel = p
        else:
            rel = p
        rel_str = str(rel).replace("\\", "/")

        # Skip infrastructure
        if rel_str.startswith(("scripts/", ".vectorstore/", ".git/")):
            return "local"

        for pattern, scope in _SCOPE_PATH_RULES_COMPILED:
            if pattern.search(rel_str):
                return scope

    # 2. Event-type classification
    if event_type and event_type in _SCOPE_EVENT_TYPES:
        return _SCOPE_EVENT_TYPES[event_type]

    # 3. Tag-based classification
    if tags:
        for tag in tags:
            for prefix, scope in _SCOPE_TAG_PREFIXES.items():
                if tag.startswith(prefix):
                    return scope

    return "local"


def get_memory_scope_filter(scope: str) -> dict[str, str | tuple[str]]:
    """Return SQL WHERE clause components for filtering events by scope.

    Args:
        scope: "project", "local", or "user"

    Returns:
        dict with 'clause' (str) and 'params' (tuple) for SQL WHERE.

    Raises:
        ValueError: If scope is not one of the valid scopes.
    """
    if scope not in MEMORY_SCOPES:
        raise ValueError(f"Invalid scope: {scope}. Must be one of {MEMORY_SCOPES}")
    return {"clause": "scope = ?", "params": (scope,)}
