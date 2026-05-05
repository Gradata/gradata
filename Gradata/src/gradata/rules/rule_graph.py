"""Rule graph — conflict and co-occurrence edges between lessons.

Lightweight adjacency list tracking relationships between rules:
- conflict: rules that contradict each other
- co_occurrence: rules that frequently fire together
- typed relationships: REINFORCES, CONTRADICTS, SPECIALIZES, GENERALIZES

Persisted as JSON (legacy edges) + SQLite (typed relationships).
"""

from __future__ import annotations

import contextlib
import json
import logging
import sqlite3
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from gradata._atomic import atomic_write_text
from gradata._tenant import tenant_for

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Relationship types
# ---------------------------------------------------------------------------


class RuleRelationType(Enum):
    """Typed relationship between two rules."""

    REINFORCES = "reinforces"
    CONTRADICTS = "contradicts"
    SPECIALIZES = "specializes"
    GENERALIZES = "generalizes"


# ---------------------------------------------------------------------------
# Contradiction detection patterns (imported from contradiction_detector)
# ---------------------------------------------------------------------------

from gradata.enhancements.contradiction_detector import (
    _ACTION_OPPOSITES,
    _POLARITY_PAIRS,
    _normalize,
)
from gradata.enhancements.similarity import _STOP_WORDS as _STOPWORDS


def _extract_keywords(text: str) -> set[str]:
    """Extract meaningful keywords, skipping stopwords."""
    words = set(_normalize(text).split())
    return words - _STOPWORDS


def _has_contradiction(desc_a: str, desc_b: str) -> bool:
    """Check if two descriptions contradict each other."""
    norm_a = _normalize(desc_a)
    norm_b = _normalize(desc_b)

    for pos, neg in _POLARITY_PAIRS:
        if (pos in norm_a and neg in norm_b) or (neg in norm_a and pos in norm_b):
            return True

    for action, opposite in _ACTION_OPPOSITES:
        if (action in norm_a and opposite in norm_b) or (opposite in norm_a and action in norm_b):
            return True

    return False


def _keyword_overlap(desc_a: str, desc_b: str) -> float:
    """Fraction of shared keywords (Jaccard similarity)."""
    kw_a = _extract_keywords(desc_a)
    kw_b = _extract_keywords(desc_b)
    if not kw_a or not kw_b:
        return 0.0
    return len(kw_a & kw_b) / len(kw_a | kw_b)


# ---------------------------------------------------------------------------
# Relationship detection
# ---------------------------------------------------------------------------


def detect_relationship(rule_a: dict, rule_b: dict) -> RuleRelationType | None:
    """Detect relationship between two rules.

    Priority order:
    1. SPECIALIZES / GENERALIZES (path hierarchy)
    2. CONTRADICTS (polarity / action opposites)
    3. REINFORCES (same category + keyword overlap > 50%)

    Returns None if no relationship detected.
    """
    path_a = rule_a.get("path", "")
    path_b = rule_b.get("path", "")
    cat_a = rule_a.get("category", "")
    cat_b = rule_b.get("category", "")
    desc_a = rule_a.get("description", "")
    desc_b = rule_b.get("description", "")

    # 1. Path hierarchy (SPECIALIZES / GENERALIZES)
    if path_a and path_b and path_a != path_b:
        if path_a.startswith(path_b + "/"):
            return RuleRelationType.SPECIALIZES
        if path_b.startswith(path_a + "/"):
            return RuleRelationType.GENERALIZES

    # 2. Contradiction detection (same category required)
    if cat_a and cat_b and cat_a == cat_b and _has_contradiction(desc_a, desc_b):
        return RuleRelationType.CONTRADICTS

    # 3. Reinforcement (same category + keyword overlap > 50%)
    if cat_a and cat_b and cat_a == cat_b and _keyword_overlap(desc_a, desc_b) > 0.5:
        return RuleRelationType.REINFORCES

    return None


# ---------------------------------------------------------------------------
# SQLite storage
# ---------------------------------------------------------------------------


def store_relationship(
    db_path: str | Path,
    rule_a_id: str,
    rule_b_id: str,
    rel_type: RuleRelationType,
    confidence: float = 0.5,
) -> None:
    """Store a typed relationship in SQLite.

    Confidence is clamped to [0.0, 1.0] before persistence per the SDK
    coding guideline ("Confidence values must be in [0.0, 1.0]").
    """
    clamped = max(0.0, min(1.0, confidence))
    _tid = tenant_for(Path(db_path).parent)
    with contextlib.closing(sqlite3.connect(str(db_path))) as conn:
        # Defensive migration: brains created before migration 001 lack tenant_id.
        with contextlib.suppress(sqlite3.OperationalError):
            conn.execute("ALTER TABLE rule_relationships ADD COLUMN tenant_id TEXT")
        with contextlib.suppress(sqlite3.OperationalError):
            conn.execute(
                "ALTER TABLE rule_relationships ADD COLUMN visibility TEXT DEFAULT 'private'"
            )
        conn.execute(
            "INSERT INTO rule_relationships "
            "(rule_a_id, rule_b_id, relationship, confidence, detected_at, tenant_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                rule_a_id,
                rule_b_id,
                rel_type.value,
                clamped,
                datetime.now(UTC).isoformat(),
                _tid,
            ),
        )
        conn.commit()


def get_related_rules(
    db_path: str | Path,
    rule_id: str,
    rel_type: RuleRelationType | None = None,
) -> list[dict]:
    """Query rules related to a given rule (bidirectional).

    Returns list of dicts with keys: related_rule_id, relationship, confidence.
    """
    with contextlib.closing(sqlite3.connect(str(db_path))) as conn:
        conn.row_factory = sqlite3.Row

        if rel_type is not None:
            rows = conn.execute(
                "SELECT rule_a_id, rule_b_id, relationship, confidence "
                "FROM rule_relationships "
                "WHERE (rule_a_id = ? OR rule_b_id = ?) AND relationship = ?",
                (rule_id, rule_id, rel_type.value),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT rule_a_id, rule_b_id, relationship, confidence "
                "FROM rule_relationships "
                "WHERE rule_a_id = ? OR rule_b_id = ?",
                (rule_id, rule_id),
            ).fetchall()

    results = []
    for row in rows:
        other_id = row["rule_b_id"] if row["rule_a_id"] == rule_id else row["rule_a_id"]
        results.append(
            {
                "related_rule_id": other_id,
                "relationship": row["relationship"],
                "confidence": row["confidence"],
            }
        )
    return results


class RuleGraph:
    """Lightweight graph of rule relationships."""

    def __init__(self, path: Path | None = None):
        self._path = path
        # edges[rule_id] = {"conflicts": {other_id: count}, "co_occurs": {other_id: count}}
        self._edges: dict[str, dict[str, dict[str, int]]] = {}
        if path and path.is_file():
            try:
                self._edges = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                _log.debug("Could not load rule graph from %s", path)

    def add_conflict(self, rule_a: str, rule_b: str) -> None:
        """Record a conflict between two rules."""
        self._ensure_node(rule_a)
        self._ensure_node(rule_b)
        self._edges[rule_a]["conflicts"][rule_b] = (
            self._edges[rule_a]["conflicts"].get(rule_b, 0) + 1
        )
        self._edges[rule_b]["conflicts"][rule_a] = (
            self._edges[rule_b]["conflicts"].get(rule_a, 0) + 1
        )

    def add_co_occurrence(self, rule_ids: list[str]) -> None:
        """Record that these rules fired together in a session."""
        for i, a in enumerate(rule_ids):
            self._ensure_node(a)
            for b in rule_ids[i + 1 :]:
                self._ensure_node(b)
                self._edges[a]["co_occurs"][b] = self._edges[a]["co_occurs"].get(b, 0) + 1
                self._edges[b]["co_occurs"][a] = self._edges[b]["co_occurs"].get(a, 0) + 1

    def get_conflicts(self, rule_id: str) -> dict[str, int]:
        """Get all rules that conflict with this one. Returns {rule_id: count}."""
        return dict(self._edges.get(rule_id, {}).get("conflicts", {}))

    def get_co_occurrences(self, rule_id: str) -> dict[str, int]:
        """Get all rules that co-occur with this one. Returns {rule_id: count}."""
        return dict(self._edges.get(rule_id, {}).get("co_occurs", {}))

    def has_conflict(self, rule_a: str, rule_b: str) -> bool:
        """Check if two rules have ever conflicted."""
        return rule_b in self._edges.get(rule_a, {}).get("conflicts", {})

    def conflict_count(self, rule_a: str, rule_b: str) -> int:
        """Number of times two rules have conflicted."""
        return self._edges.get(rule_a, {}).get("conflicts", {}).get(rule_b, 0)

    def save(self) -> None:
        """Persist graph to disk."""
        if self._path:
            atomic_write_text(self._path, json.dumps(self._edges, indent=2))

    def _ensure_node(self, rule_id: str) -> None:
        if rule_id not in self._edges:
            self._edges[rule_id] = {"conflicts": {}, "co_occurs": {}}

    @property
    def node_count(self) -> int:
        return len(self._edges)

    @property
    def edge_count(self) -> int:
        count = 0
        for node in self._edges.values():
            count += len(node.get("conflicts", {}))
            count += len(node.get("co_occurs", {}))
        return count // 2  # Each edge counted twice
