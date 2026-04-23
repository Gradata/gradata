"""
Passive Memory Extraction — Extract facts from any conversation.
================================================================
Layer 1 Enhancement: pure logic, stdlib only.

Stolen from: Mem0's two-phase extract-then-update pipeline.

The correction pipeline only learns from user edits. This module captures
ALL useful information from conversations — facts, preferences, entities,
relationships — not just behavioral corrections.

Two-phase pipeline:
  1. EXTRACT: Identify candidate facts/preferences from messages
  2. RECONCILE: Compare candidates against existing facts, decide
     ADD / UPDATE / INVALIDATE / SKIP

The extraction uses rule-based heuristics (no LLM dependency for the SDK).
Cloud mode can use LLM-powered extraction for higher quality.

Usage:
    extractor = MemoryExtractor()
    facts = extractor.extract(messages)
    actions = extractor.reconcile(facts, existing_facts)

    for action in actions:
        if action.op == "add":
            store(action.fact)
        elif action.op == "update":
            update(action.target_id, action.fact)
        elif action.op == "invalidate":
            invalidate(action.target_id, reason=action.reason)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class ExtractedFact:
    """A candidate fact extracted from conversation."""

    content: str  # Natural language fact
    fact_type: str  # preference, entity, relationship, action_item, temporal
    confidence: float = 0.7  # Extraction confidence (0-1)
    source_role: str = "user"  # Who said it: user, assistant
    entities: list[str] = field(default_factory=list)  # Named entities mentioned
    timestamp: str = ""


@dataclass
class ReconcileAction:
    """Action to take after comparing extracted fact against existing facts."""

    op: str  # add, update, invalidate, skip
    fact: ExtractedFact
    target_id: str | None = None  # ID of existing fact to update/invalidate
    reason: str = ""  # Why this action
    supersedes: str | None = None  # ID of fact being superseded (for temporal tracking)


# ---------------------------------------------------------------------------
# Extraction patterns (rule-based, no LLM)
# ---------------------------------------------------------------------------

# Preference patterns: "I prefer X", "I like X", "don't use X", "always X"
_PREFERENCE_PATTERNS = [
    re.compile(
        r"(?:i|we)\s+(?:prefer|like|want|need|love|hate|dislike|avoid)\s+(.+?)(?:\.|$)", re.I
    ),
    re.compile(
        r"(?:always|never|don't|do not)\s+(?:use|include|add|write|mention|say)\s+(.+?)(?:\.|$)",
        re.I,
    ),
    re.compile(r"(?:instead of|rather than)\s+(.+?)(?:,|\.|\s+use)", re.I),
]

# Entity patterns: proper nouns, company names, tool names
_ENTITY_PATTERN = re.compile(r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\b")

# Action item patterns: "follow up", "schedule", "send", "check"
_ACTION_PATTERNS = [
    re.compile(r"(?:need to|should|will|going to|have to|must)\s+(.+?)(?:\.|$)", re.I),
    re.compile(r"(?:follow up|schedule|send|check|review|prepare|draft)\s+(.+?)(?:\.|$)", re.I),
    re.compile(
        r"(?:by|before|on|until)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday|\d{1,2}[/-]\d{1,2})",
        re.I,
    ),
]

# Temporal patterns: dates, deadlines, timeframes
_TEMPORAL_PATTERNS = [
    re.compile(
        r"(?:meeting|call|demo|appointment)\s+(?:on|at|scheduled for)\s+(.+?)(?:\.|$)", re.I
    ),
    re.compile(r"(?:deadline|due|expires?)\s+(?:on|by|is)?\s*(.+?)(?:\.|$)", re.I),
]

# Relationship patterns: "X works at Y", "X is the Y at Z"
_RELATIONSHIP_PATTERNS = [
    re.compile(r"(\w+(?:\s+\w+)?)\s+(?:works at|is at|joined)\s+(.+?)(?:\.|$)", re.I),
    re.compile(
        r"(\w+(?:\s+\w+)?)\s+is\s+(?:the\s+)?(\w+(?:\s+\w+)?)\s+(?:at|of|for)\s+(.+?)(?:\.|$)", re.I
    ),
]


class MemoryExtractor:
    """Extract facts from conversation messages using rule-based heuristics.

    This is the SDK's local extraction. Cloud mode can swap in an
    LLM-powered extractor for higher quality.
    """

    def extract(self, messages: list[dict]) -> list[ExtractedFact]:
        """Extract candidate facts from a conversation.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.

        Returns:
            List of ExtractedFact objects.
        """
        facts: list[ExtractedFact] = []
        now = datetime.now(UTC).isoformat()

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if not content:
                continue

            # Extract preferences (highest value for behavioral adaptation)
            for pattern in _PREFERENCE_PATTERNS:
                for match in pattern.finditer(content):
                    fact_text = match.group(0).strip()
                    if len(fact_text) > 10:  # Skip trivially short matches
                        facts.append(
                            ExtractedFact(
                                content=fact_text,
                                fact_type="preference",
                                confidence=0.8,
                                source_role=role,
                                entities=self._extract_entities(fact_text),
                                timestamp=now,
                            )
                        )

            # Extract action items (prospective memory)
            for pattern in _ACTION_PATTERNS:
                for match in pattern.finditer(content):
                    fact_text = match.group(0).strip()
                    if len(fact_text) > 10 and role == "user":
                        facts.append(
                            ExtractedFact(
                                content=fact_text,
                                fact_type="action_item",
                                confidence=0.6,
                                source_role=role,
                                entities=self._extract_entities(fact_text),
                                timestamp=now,
                            )
                        )

            # Extract temporal facts (meetings, deadlines)
            for pattern in _TEMPORAL_PATTERNS:
                for match in pattern.finditer(content):
                    fact_text = match.group(0).strip()
                    facts.append(
                        ExtractedFact(
                            content=fact_text,
                            fact_type="temporal",
                            confidence=0.7,
                            source_role=role,
                            timestamp=now,
                        )
                    )

            # Extract relationships
            for pattern in _RELATIONSHIP_PATTERNS:
                for match in pattern.finditer(content):
                    fact_text = match.group(0).strip()
                    entities = [g for g in match.groups() if g]
                    facts.append(
                        ExtractedFact(
                            content=fact_text,
                            fact_type="relationship",
                            confidence=0.6,
                            source_role=role,
                            entities=entities,
                            timestamp=now,
                        )
                    )

        # Deduplicate by content similarity
        return self._deduplicate(facts)

    def reconcile(
        self,
        candidates: list[ExtractedFact],
        existing: list[dict],
    ) -> list[ReconcileAction]:
        """Compare extracted facts against existing facts and decide actions.

        Stolen from Mem0's ADD/UPDATE/DELETE/NOOP pattern, adapted
        with temporal preservation (mark invalid, don't delete).

        Args:
            candidates: Newly extracted facts.
            existing: Existing facts as dicts with 'id', 'content', 'fact_type' keys.

        Returns:
            List of ReconcileAction objects.
        """
        actions: list[ReconcileAction] = []

        for candidate in candidates:
            match = self._find_similar(candidate, existing)

            if match is None:
                # No similar fact exists — ADD
                actions.append(
                    ReconcileAction(
                        op="add",
                        fact=candidate,
                        reason="New fact, no similar existing entry",
                    )
                )
            elif self._is_contradiction(candidate, match):
                # Contradicts existing — INVALIDATE old + ADD new
                # Temporal preservation: don't delete, mark as superseded
                actions.append(
                    ReconcileAction(
                        op="invalidate",
                        fact=candidate,
                        target_id=match.get("id"),
                        reason="Superseded by newer information",
                        supersedes=match.get("id"),
                    )
                )
                actions.append(
                    ReconcileAction(
                        op="add",
                        fact=candidate,
                        reason=f"Replaces invalidated fact {match.get('id')}",
                        supersedes=match.get("id"),
                    )
                )
            elif self._is_enrichment(candidate, match):
                # Adds new info to existing — UPDATE
                actions.append(
                    ReconcileAction(
                        op="update",
                        fact=candidate,
                        target_id=match.get("id"),
                        reason="Enriches existing fact with new details",
                    )
                )
            else:
                # Already well-represented — SKIP
                actions.append(
                    ReconcileAction(
                        op="skip",
                        fact=candidate,
                        target_id=match.get("id"),
                        reason="Already captured",
                    )
                )

        return actions

    # ── Private helpers ──────────────────────────────────────────────

    def _extract_entities(self, text: str) -> list[str]:
        """Extract named entities (proper nouns) from text."""
        # Simple heuristic: capitalized multi-word sequences
        return list(set(_ENTITY_PATTERN.findall(text)))[:5]

    def _deduplicate(self, facts: list[ExtractedFact]) -> list[ExtractedFact]:
        """Remove near-duplicate facts (same content, keep highest confidence)."""
        seen: dict[str, ExtractedFact] = {}
        for fact in facts:
            key = fact.content.lower().strip()[:80]
            if key not in seen or fact.confidence > seen[key].confidence:
                seen[key] = fact
        return list(seen.values())

    def _find_similar(
        self,
        candidate: ExtractedFact,
        existing: list[dict],
    ) -> dict | None:
        """Find the most similar existing fact, if any."""
        candidate_words = set(candidate.content.lower().split())
        best_match = None
        best_overlap = 0.0

        for fact in existing:
            fact_words = set(fact.get("content", "").lower().split())
            if not fact_words:
                continue

            overlap = len(candidate_words & fact_words)
            union = len(candidate_words | fact_words)
            jaccard = overlap / union if union > 0 else 0

            if jaccard > 0.5 and jaccard > best_overlap:
                best_overlap = jaccard
                best_match = fact

        return best_match

    def _is_contradiction(self, candidate: ExtractedFact, existing: dict) -> bool:
        """Check if candidate contradicts existing fact."""
        # Simple heuristic: negation words differ
        neg_words = {"not", "never", "don't", "doesn't", "didn't", "no", "without", "avoid"}
        cand_has_neg = bool(set(candidate.content.lower().split()) & neg_words)
        exist_has_neg = bool(set(existing.get("content", "").lower().split()) & neg_words)
        return cand_has_neg != exist_has_neg

    def _is_enrichment(self, candidate: ExtractedFact, existing: dict) -> bool:
        """Check if candidate adds new info to existing fact."""
        cand_words = set(candidate.content.lower().split())
        exist_words = set(existing.get("content", "").lower().split())
        new_words = cand_words - exist_words
        # If candidate has >3 new words beyond what exists, it's enrichment
        return len(new_words) > 3
