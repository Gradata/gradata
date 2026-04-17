"""
Rule engine data models.
========================
Defines :class:`AppliedRule` — the output unit of the rule engine.
"""

from __future__ import annotations

from dataclasses import dataclass

from gradata._types import Lesson


@dataclass
class AppliedRule:
    """A lesson that has been scored and formatted for prompt injection.

    Attributes:
        rule_id: Stable opaque identifier derived from category and
            description hash, e.g. ``"DRAFTING:0042"``.
        lesson: The source :class:`~gradata._self_improvement.Lesson`.
        relevance: Scope match score in [0.0, 1.0] from
            :func:`~gradata._scope.scope_matches`.
        instruction: Human-readable rule text for direct injection into an
            LLM prompt, e.g.
            ``"[RULE:0.95] DRAFTING: Always include pricing in first email"``.
    """

    rule_id: str
    lesson: Lesson
    relevance: float
    instruction: str
