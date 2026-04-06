"""
CARL — Behavioral Contracts per Domain with Priority Tiers.
=============================================================
SDK LAYER: Layer 1 (enhancements). Pure Python.

Contracts define behavioral constraints that apply to specific task types
within a domain. The ContractRegistry matches incoming tasks to relevant
contracts and returns applicable constraints for prompt injection.

v2: Adds priority tiers (MUST/SHOULD/MAY) adapted from ChristopherKahler/paul's CARL
rule system. MUST constraints are blocking, SHOULD constraints are
warnings, MAY constraints are suggestions.

Usage::

    from gradata.enhancements.carl import (
        BehavioralContract, ContractRegistry, RulePriority,
        PrioritizedConstraint,
    )

    contract = BehavioralContract(
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
    """Enforcement gradient for CARL constraints.

    Adapted from ChristopherKahler/paul's CARL rule system:
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
class BehavioralContract:
    """A behavioral constraint for a specific domain and task type.

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


class ContractRegistry:
    """Registry for behavioral contracts. Matches tasks to constraints."""

    def __init__(self) -> None:
        self._contracts: list[BehavioralContract] = []

    def register(self, contract: BehavioralContract) -> None:
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
        """Check whether any MUST constraints are violated.

        Returns True if any applicable MUST constraints exist for this task.
        """
        must_constraints = self.get_prioritized_constraints(
            task, min_priority=RulePriority.MUST
        )
        return any(c.priority == RulePriority.MUST for c in must_constraints)

    def get_contracts_for_domain(self, domain: str) -> list[BehavioralContract]:
        """Return all contracts for a specific domain."""
        return [c for c in self._contracts if c.domain == domain]

    def format_constraints_prompt(self, task: str) -> str:
        """Format applicable constraints as a prompt injection block.

        Groups constraints by priority tier for clear enforcement.
        """
        constraints = self.get_prioritized_constraints(task)
        if not constraints:
            return ""

        lines = ["<carl-constraints>"]

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

        lines.append("</carl-constraints>")
        return "\n".join(lines)
