"""
Behavioral Engine — Directives per Domain with Priority Tiers.
================================================================
SDK LAYER: Layer 1 (enhancements). Pure Python.

Directives define behavioral constraints that apply to specific task types
within a domain. The DirectiveRegistry matches incoming tasks to relevant
directives and returns applicable constraints for prompt injection.

Priority tiers (MUST/SHOULD/MAY): MUST constraints are blocking, SHOULD
constraints are warnings, MAY constraints are suggestions.

Usage::

    from gradata.enhancements.behavioral_engine import (
        Directive, DirectiveRegistry, RulePriority,
        PrioritizedConstraint,
    )

    directive = Directive(
        name="no-deploy-friday",
        domain="devops",
        trigger_keywords=["deploy", "release"],
        constraints=[
            PrioritizedConstraint(
                rule="Never deploy on Friday after 3pm",
                priority=RulePriority.MUST,
            ),
            PrioritizedConstraint(
                rule="Prefer blue-green deployment",
                priority=RulePriority.SHOULD,
            ),
        ],
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class RulePriority(Enum):
    """Enforcement gradient for directive constraints.

    - MUST: Blocking. Violation stops execution.
    - SHOULD: Warning. Violation is logged but execution continues.
    - MAY: Suggestion. Informational only.
    """

    MUST = "must"
    SHOULD = "should"
    MAY = "may"


@dataclass
class PrioritizedConstraint:
    """A constraint with an enforcement priority level.

    Attributes:
        rule: The constraint text.
        priority: Enforcement level (MUST/SHOULD/MAY).
        rationale: Why this constraint exists (helps edge-case judgment).
    """

    rule: str
    priority: RulePriority = RulePriority.SHOULD
    rationale: str = ""

    def __str__(self) -> str:
        return f"[{self.priority.value.upper()}] {self.rule}"


@dataclass
class ConstraintViolation:
    """A detected violation of a constraint.

    Attributes:
        constraint: The violated constraint.
        context: What triggered the violation.
        blocking: Whether this violation should stop execution.
    """

    constraint: PrioritizedConstraint
    context: str = ""

    @property
    def blocking(self) -> bool:
        """MUST violations are blocking; SHOULD and MAY are not."""
        return self.constraint.priority == RulePriority.MUST


@dataclass
class Directive:
    """A behavioral directive for a specific domain and task type.

    Supports both legacy string constraints and new PrioritizedConstraint
    objects. Legacy strings are auto-wrapped as SHOULD priority.
    """

    name: str
    domain: str
    trigger_keywords: list[str] = field(default_factory=list)
    constraints: list[PrioritizedConstraint | str] = field(default_factory=list)

    def get_prioritized(self) -> list[PrioritizedConstraint]:
        """Return all constraints as PrioritizedConstraint objects.

        Legacy string constraints are wrapped as SHOULD priority.
        """
        result: list[PrioritizedConstraint] = []
        for c in self.constraints:
            if isinstance(c, str):
                result.append(PrioritizedConstraint(rule=c, priority=RulePriority.SHOULD))
            else:
                result.append(c)
        return result

    def get_by_priority(self, priority: RulePriority) -> list[PrioritizedConstraint]:
        """Return constraints filtered by priority level."""
        return [c for c in self.get_prioritized() if c.priority == priority]

    @property
    def must_rules(self) -> list[PrioritizedConstraint]:
        """Return only MUST (blocking) constraints."""
        return self.get_by_priority(RulePriority.MUST)

    @property
    def should_rules(self) -> list[PrioritizedConstraint]:
        """Return only SHOULD (warning) constraints."""
        return self.get_by_priority(RulePriority.SHOULD)

    @property
    def may_rules(self) -> list[PrioritizedConstraint]:
        """Return only MAY (suggestion) constraints."""
        return self.get_by_priority(RulePriority.MAY)


class DirectiveRegistry:
    """Registry for behavioral contracts. Matches tasks to constraints."""

    def __init__(self) -> None:
        self._contracts: list[Directive] = []

    def register(self, contract: Directive) -> None:
        """Add a behavioral contract to the registry."""
        self._contracts.append(contract)

    def stats(self) -> dict:
        """Return registry statistics."""
        by_priority: dict[str, int] = {"must": 0, "should": 0, "may": 0}
        for contract in self._contracts:
            for c in contract.get_prioritized():
                by_priority[c.priority.value] += 1

        return {
            "total_contracts": len(self._contracts),
            "domains": list(self.domains),
            "constraints_by_priority": by_priority,
        }

    @property
    def domains(self) -> set[str]:
        """Return set of all registered domains."""
        return {c.domain for c in self._contracts}

    def get_constraints(self, task: str) -> list[str]:
        """Return constraint strings applicable to a task.

        Legacy API: returns flat list of constraint rule strings.
        Matches task against trigger_keywords of all contracts.
        """
        task_lower = task.lower()
        constraints: list[str] = []
        for contract in self._contracts:
            if any(kw.lower() in task_lower for kw in contract.trigger_keywords):
                for c in contract.get_prioritized():
                    constraints.append(c.rule)
        return constraints

    def get_prioritized_constraints(
        self,
        task: str,
        min_priority: RulePriority | None = None,
    ) -> list[PrioritizedConstraint]:
        """Return prioritized constraints applicable to a task.

        Args:
            task: The task description to match against.
            min_priority: If set, only return constraints at this level
                or higher (MUST > SHOULD > MAY).

        Returns:
            List of PrioritizedConstraint objects, ordered by priority
            (MUST first, then SHOULD, then MAY).
        """
        priority_order = {RulePriority.MUST: 0, RulePriority.SHOULD: 1, RulePriority.MAY: 2}
        min_order = priority_order.get(min_priority, 2) if min_priority else 2

        task_lower = task.lower()
        constraints: list[PrioritizedConstraint] = []

        for contract in self._contracts:
            if any(kw.lower() in task_lower for kw in contract.trigger_keywords):
                for c in contract.get_prioritized():
                    if priority_order[c.priority] <= min_order:
                        constraints.append(c)

        constraints.sort(key=lambda c: priority_order[c.priority])
        return constraints

    def has_blocking_violations(self, task: str) -> bool:
        """Check whether any MUST constraints apply to this task.

        Returns True if any applicable MUST constraints exist for this task.
        """
        return bool(self.get_prioritized_constraints(task, min_priority=RulePriority.MUST))

    def format_constraints_prompt(self, task: str) -> str:
        """Format applicable constraints as a prompt injection block.

        Groups constraints by priority tier for clear enforcement.
        """
        constraints = self.get_prioritized_constraints(task)
        if not constraints:
            return ""

        lines = ["<behavioral-directives>"]

        must = [c for c in constraints if c.priority == RulePriority.MUST]
        should = [c for c in constraints if c.priority == RulePriority.SHOULD]
        may = [c for c in constraints if c.priority == RulePriority.MAY]

        if must:
            lines.append("  [MUST — blocking, violation stops execution]")
            for c in must:
                lines.append(f"    - {c.rule}")
                if c.rationale:
                    lines.append(f"      Why: {c.rationale}")

        if should:
            lines.append("  [SHOULD — warning, log but continue]")
            for c in should:
                lines.append(f"    - {c.rule}")

        if may:
            lines.append("  [MAY — suggestion, informational]")
            for c in may:
                lines.append(f"    - {c.rule}")

        lines.append("</behavioral-directives>")
        return "\n".join(lines)


@dataclass
class Disposition:
    """Soft behavioral tendencies per domain (1-5 scales).

    Unlike Hindsight's static manual scales, Gradata dispositions evolve
    from corrections. Each scale maps to concrete behavioral instructions.
    """

    skepticism: float = 3.0
    literalism: float = 3.0
    empathy: float = 3.0

    def clamp(self) -> None:
        self.skepticism = max(1.0, min(5.0, self.skepticism))
        self.literalism = max(1.0, min(5.0, self.literalism))
        self.empathy = max(1.0, min(5.0, self.empathy))

    def behavioral_instructions(self) -> list[str]:
        """Map disposition values to concrete prompt instructions."""
        instructions: list[str] = []
        if self.skepticism >= 4.0:
            instructions.append(
                "Cross-reference claims across multiple sources before stating them."
            )
        elif self.skepticism <= 2.0:
            instructions.append("Trust provided context without excessive verification.")
        if self.literalism >= 4.0:
            instructions.append(
                "Stick to explicitly stated facts. Do not infer beyond what is written."
            )
        elif self.literalism <= 2.0:
            instructions.append(
                "Synthesize and infer between the lines. Read intent, not just words."
            )
        if self.empathy >= 4.0:
            instructions.append("Acknowledge emotional context and adjust tone accordingly.")
        elif self.empathy <= 2.0:
            instructions.append("Keep responses factual and clinical. Focus on data over feelings.")
        return instructions

    def format_for_prompt(self) -> str:
        """Format disposition as a prompt injection block."""
        lines = [
            f"Disposition: skepticism={self.skepticism:.1f}, literalism={self.literalism:.1f}, empathy={self.empathy:.1f}"
        ]
        instructions = self.behavioral_instructions()
        if instructions:
            lines.extend(f"  - {inst}" for inst in instructions)
        return "\n".join(lines)


# Severity-based deltas for disposition updates
_SEVERITY_DELTAS = {
    "trivial": 0.1,
    "minor": 0.15,
    "moderate": 0.2,
    "major": 0.25,
    "rewrite": 0.3,
}


# Maps edit_classifier categories to disposition adjustments
_CORRECTION_DISPOSITION_MAP: dict[str, tuple[str, float]] = {
    "too_literal": ("literalism", -1.0),
    "too_inferential": ("literalism", 1.0),
    "too_trusting": ("skepticism", 1.0),
    "too_skeptical": ("skepticism", -1.0),
    "too_cold": ("empathy", 1.0),
    "too_warm": ("empathy", -1.0),
    "hallucination": ("skepticism", 1.0),
    "missed_context": ("literalism", -1.0),
}


class DispositionTracker:
    """Tracks and evolves dispositions per domain from corrections."""

    def __init__(self) -> None:
        self._dispositions: dict[str, Disposition] = {}

    def get(self, domain: str = "global") -> Disposition:
        if domain not in self._dispositions:
            self._dispositions[domain] = Disposition()
        return self._dispositions[domain]

    def update_from_correction(
        self,
        domain: str,
        category: str,
        severity: str = "minor",
    ) -> Disposition:
        """Update disposition based on a correction category and severity."""
        disp = self.get(domain)
        mapping = _CORRECTION_DISPOSITION_MAP.get(category)
        if mapping is None:
            return disp
        attr, direction = mapping
        delta = _SEVERITY_DELTAS.get(severity, 0.15) * direction
        current = getattr(disp, attr)
        setattr(disp, attr, current + delta)
        disp.clamp()
        return disp

    @property
    def domains(self) -> list[str]:
        return list(self._dispositions.keys())

    def to_dict(self) -> dict[str, dict[str, float]]:
        return {
            domain: {"skepticism": d.skepticism, "literalism": d.literalism, "empathy": d.empathy}
            for domain, d in self._dispositions.items()
        }

    @classmethod
    def from_dict(cls, data: dict[str, dict[str, float]]) -> DispositionTracker:
        tracker = cls()
        for domain, vals in data.items():
            d = Disposition(
                skepticism=vals.get("skepticism", 3.0),
                literalism=vals.get("literalism", 3.0),
                empathy=vals.get("empathy", 3.0),
            )
            d.clamp()
            tracker._dispositions[domain] = d
        return tracker


# Backward-compat aliases for code that still uses the old names
BehavioralContract = Directive
ContractRegistry = DirectiveRegistry
