"""Persistent Memory Pattern — episodic, semantic, procedural memory types."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_TYPES: frozenset[str] = frozenset({
    "episodic",     # What happened (interactions, outcomes)
    "semantic",     # What is true (facts, knowledge)
    "procedural",   # How to do things (workflows, patterns)
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Return current UTC time as an ISO 8601 string."""
    return datetime.now(UTC).isoformat()


def _parse_iso(ts: str) -> datetime:
    """Parse an ISO 8601 timestamp (with or without microseconds / 'Z' suffix)."""
    # Normalise the trailing 'Z' that Python's fromisoformat() rejects before 3.11
    normalised = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(normalised)


# ---------------------------------------------------------------------------
# Core data class
# ---------------------------------------------------------------------------


@dataclass
class Memory:
    """A single unit of brain memory."""

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
        """Return age in fractional days since creation (UTC)."""
        created_dt = _parse_iso(self.created)
        delta = datetime.now(UTC) - created_dt
        return delta.total_seconds() / 86_400


# ---------------------------------------------------------------------------
# MemoryStore protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class MemoryStore(Protocol):
    """Backend-agnostic interface for memory persistence."""

    def store(self, memory: Memory) -> str:
        """Persist a memory and return its id."""
        ...

    def retrieve(
        self,
        query: str,
        types: list[str] | None = None,
        limit: int = 10,
    ) -> list[Memory]:
        """Retrieve memories matching ``query``."""
        ...

    def update(self, memory_id: str, content: str) -> None:
        """Replace the content of an existing memory in place."""
        ...

    def delete(self, memory_id: str) -> None:
        """Remove a memory permanently."""
        ...


# ---------------------------------------------------------------------------
# InMemoryStore — dict-based reference implementation
# ---------------------------------------------------------------------------


class InMemoryStore:
    """Dictionary-backed :class:`MemoryStore` for testing and small brains."""

    def __init__(self, initial: dict[str, Memory] | None = None) -> None:
        self._data: dict[str, Memory] = dict(initial) if initial else {}

    # -- MemoryStore interface -----------------------------------------------

    def store(self, memory: Memory) -> str:
        """Persist ``memory`` and return its ``id``."""
        self._data[memory.id] = memory
        return memory.id

    def retrieve(
        self,
        query: str,
        types: list[str] | None = None,
        limit: int = 10,
    ) -> list[Memory]:
        """Return memories whose content contains ``query`` (case-insensitive)."""
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
        """Replace content of an existing memory."""
        if memory_id not in self._data:
            raise KeyError(f"Memory not found: {memory_id!r}")
        if not content:
            raise ValueError("Memory content must not be empty.")
        self._data[memory_id].content = content

    def delete(self, memory_id: str) -> None:
        """Remove a memory from the store."""
        if memory_id not in self._data:
            raise KeyError(f"Memory not found: {memory_id!r}")
        del self._data[memory_id]

    # -- Extras (not part of the protocol, but useful) -----------------------

    def all(self) -> list[Memory]:
        """Return all stored memories (unordered)."""
        return list(self._data.values())

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return f"InMemoryStore({len(self._data)} memories)"


# ---------------------------------------------------------------------------
# EpisodicMemory — what happened
# ---------------------------------------------------------------------------


class EpisodicMemory:
    """Episodic memory layer — records of events, interactions, and outcomes."""

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
        """Record an episodic event."""
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
        """Retrieve episodic memories matching ``query``."""
        return self._store.retrieve(query, types=[self.memory_type], limit=limit)

    def decay(self, max_age_days: int = 30, min_reinforcements: int = 1) -> list[str]:
        """Remove stale, unreinforced episodic memories."""
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
    """Semantic memory layer — facts, domain knowledge, and entity attributes."""

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
        """Record a semantic fact."""
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
        """Retrieve semantic facts matching ``query``."""
        return self._store.retrieve(query, types=[self.memory_type], limit=limit)

    def update(self, memory_id: str, content: str) -> None:
        """Revise an existing semantic fact in place."""
        self._store.update(memory_id, content)

    def conflict_resolve(self, memory_a: Memory, memory_b: Memory) -> Memory:
        """Resolve a conflict between two semantic memories for the same fact."""
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
    """Procedural memory layer — workflows, patterns, and effective techniques."""

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
        """Record a procedural pattern or workflow."""
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
        """Retrieve procedural patterns matching ``query``."""
        return self._store.retrieve(query, types=[self.memory_type], limit=limit)

    def reinforce(self, memory_id: str) -> int:
        """Increment the reinforcement count for a procedural memory."""
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
        """Remove stale, unreinforced procedural patterns."""
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
    """Unified interface across all three memory types."""

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
        """Store a memory of the given type."""
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
        """Retrieve memories matching ``query``, optionally filtered by type."""
        return self._store.retrieve(query, types=types, limit=limit)

    def update(self, memory_id: str, content: str) -> None:
        """Replace the content of a memory, regardless of type."""
        self._store.update(memory_id, content)

    # -- Lifecycle -----------------------------------------------------------

    def decay(
        self,
        max_age_days: int = 30,
        min_reinforcements: int = 1,
    ) -> list[str]:
        """Prune memories that are both old and unreinforced."""
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
        """Resolve a conflict between two memories for the same fact."""
        return self.semantic.conflict_resolve(memory_a, memory_b)

    # -- Introspection -------------------------------------------------------

    def stats(self) -> dict:
        """Return a summary of current memory state."""
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
            count = len(self._store) if hasattr(self._store, "__len__") else "?"  # type: ignore[arg-type]
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
    """Auto-classify what scope a piece of brain data belongs to."""
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
    """Return SQL WHERE clause components for filtering events by scope."""
    if scope not in MEMORY_SCOPES:
        raise ValueError(f"Invalid scope: {scope}. Must be one of {MEMORY_SCOPES}")
    return {"clause": "scope = ?", "params": (scope,)}
