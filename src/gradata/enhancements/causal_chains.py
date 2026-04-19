"""Layer-1 provenance graph: tracks which corrections produced which rules/
behaviors, enabling ablation testing + provenance queries.
Adapted from Hindsight causal relations.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CausalRelation(StrEnum):
    CORRECTION_TO_RULE = "correction_to_rule"  # Correction produced this rule
    RULE_TO_BEHAVIOR = "rule_to_behavior"  # Rule changed this behavior
    CORRECTION_CHAIN = "correction_chain"  # Corrections share root cause
    REINFORCEMENT = "reinforcement"  # Correction reinforced existing rule


@dataclass
class CausalLink:
    """A causal relationship between two events in the learning pipeline."""

    source_id: str  # Event/correction/rule that caused this
    target_id: str  # Event/correction/rule that was caused
    relation: CausalRelation  # Type of causal link
    strength: float = 1.0  # 0.0-1.0 confidence in the link
    session: int = 0


class CausalChain:
    """Tracks causal links between corrections, rules, and behaviors."""

    def __init__(self) -> None:
        self._links: list[CausalLink] = []

    def add_link(
        self,
        source_id: str,
        target_id: str,
        relation: CausalRelation,
        strength: float = 1.0,
        session: int = 0,
    ) -> CausalLink:
        link = CausalLink(source_id, target_id, relation, strength, session)
        self._links.append(link)
        return link

    def trace_rule_origin(self, rule_id: str) -> list[CausalLink]:
        """Trace backward: what corrections produced this rule?"""
        return [
            l
            for l in self._links
            if l.target_id == rule_id
            and l.relation in (CausalRelation.CORRECTION_TO_RULE, CausalRelation.REINFORCEMENT)
        ]

    def trace_rule_impact(self, rule_id: str) -> list[CausalLink]:
        """Trace forward: what behaviors did this rule change?"""
        return [
            l
            for l in self._links
            if l.source_id == rule_id and l.relation == CausalRelation.RULE_TO_BEHAVIOR
        ]

    def find_correction_chains(self, correction_id: str) -> list[CausalLink]:
        """Find corrections sharing a root cause with this one."""
        return [
            l
            for l in self._links
            if (l.source_id == correction_id or l.target_id == correction_id)
            and l.relation == CausalRelation.CORRECTION_CHAIN
        ]

    def get_rule_provenance(self, rule_id: str) -> dict:
        """Full provenance for a rule: corrections that built it + behaviors it changed.

        This is the data structure ablation testing needs to prove causation.
        """
        origins = self.trace_rule_origin(rule_id)
        impacts = self.trace_rule_impact(rule_id)
        return {
            "rule_id": rule_id,
            "correction_sources": [
                {"id": l.source_id, "strength": l.strength, "session": l.session} for l in origins
            ],
            "behavioral_impacts": [
                {"id": l.target_id, "strength": l.strength, "session": l.session} for l in impacts
            ],
            "total_evidence": len(origins) + len(impacts),
        }

    def to_list(self) -> list[dict]:
        """Serialize all links."""
        return [
            {
                "source_id": l.source_id,
                "target_id": l.target_id,
                "relation": l.relation.value,
                "strength": l.strength,
                "session": l.session,
            }
            for l in self._links
        ]

    @classmethod
    def from_list(cls, data: list[dict]) -> CausalChain:
        """Deserialize from list of dicts."""
        chain = cls()
        for item in data:
            chain._links.append(
                CausalLink(
                    source_id=item["source_id"],
                    target_id=item["target_id"],
                    relation=CausalRelation(item["relation"]),
                    strength=item.get("strength", 1.0),
                    session=item.get("session", 0),
                )
            )
        return chain

    @property
    def link_count(self) -> int:
        return len(self._links)
