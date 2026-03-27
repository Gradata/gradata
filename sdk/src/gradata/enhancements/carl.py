"""
CARL — Context-Aware Rule Language (full governance system).
=============================================================
Enhancement Layer: builds on patterns/scope.py + patterns/rule_engine.py

Rebuilt from the original 5-layer CARL system (.carl/ directory).
The SDK version preserves all original capabilities:

1. Manifest routing (ALWAYS_ON / RECALL / EXCLUDE with priority tiers)
2. Skill contracts (READS / WRITES / REQUIRES declarations)
3. Hierarchical rules (GLOBAL > CONSTITUTION > DOMAIN > SAFETY)
4. Safety rule immutability (CRITICAL priority cannot be overridden)
5. Context-bracket rules (FRESH / MODERATE / DEPLETED / CRITICAL)

Domain-agnostic: works for sales, recruiting, engineering, or any domain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

# ---------------------------------------------------------------------------
# Priority tiers (from .carl/manifest)
# ---------------------------------------------------------------------------

class Priority(StrEnum):
    """Rule priority tiers. CRITICAL rules cannot be overridden."""
    CRITICAL = "critical"   # Safety rules — immutable
    HIGH = "high"           # Always loaded at startup
    NORMAL = "normal"       # Loaded on keyword match
    LOW = "low"             # Advisory only


class LoadMode(StrEnum):
    """When to load a contract."""
    ALWAYS_ON = "always_on"   # Loaded every session
    RECALL = "recall"         # Loaded when keywords match
    DORMANT = "dormant"       # Disabled but preserved


class ContractState(StrEnum):
    """Contract lifecycle state."""
    ACTIVE = "active"
    SHADOW = "shadow"     # Testing — loaded but not enforced
    DORMANT = "dormant"   # Disabled


# ---------------------------------------------------------------------------
# Skill contracts (READS / WRITES / REQUIRES)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SkillContract:
    """Declares data dependencies for a domain skill.

    From original CARL: DEMOPREP_READS, DEMOPREP_WRITES, DEMOPREP_REQUIRES.
    Makes domains portable — dependencies are explicit, not implicit.
    """
    reads: list[str] = field(default_factory=list)     # files/patterns this skill reads
    writes: list[str] = field(default_factory=list)     # files/patterns this skill writes
    requires: list[str] = field(default_factory=list)   # preconditions that must be satisfied


# ---------------------------------------------------------------------------
# Behavioral contract (full version)
# ---------------------------------------------------------------------------

@dataclass
class BehavioralContract:
    """A behavioral governance rule that travels with the brain.

    Restores all 5 layers from the original CARL system.
    """
    name: str
    domain: str = ""                             # empty = universal
    # Manifest routing
    load_mode: LoadMode = LoadMode.RECALL
    state: ContractState = ContractState.ACTIVE
    priority: Priority = Priority.NORMAL
    trigger_keywords: list[str] = field(default_factory=list)
    exclude_keywords: list[str] = field(default_factory=list)
    # Rules
    constraints: list[str] = field(default_factory=list)
    context_files: list[str] = field(default_factory=list)
    # Skill contract (portable dependencies)
    skill: SkillContract = field(default_factory=SkillContract)
    # Hierarchy
    rule_level: str = "domain"    # global, constitution, domain, safety


# ---------------------------------------------------------------------------
# Constitution rules (meta-governance)
# ---------------------------------------------------------------------------

CONSTITUTION = [
    "Every rule must be testable — if you can't verify compliance, the rule is invalid.",
    "No rule may weaken, override, or contradict a CRITICAL-priority rule without explicit owner approval.",
    "Every rule must trace to a source (correction event, owner directive, or published research).",
    "Rule count per domain must stay under 20. Complexity kills compliance.",
    "Rules with zero applications across 10+ sessions are flagged for removal.",
]


# ---------------------------------------------------------------------------
# Context brackets (budget-aware rule loading)
# ---------------------------------------------------------------------------

@dataclass
class ContextBracket:
    """Rules that vary by context budget remaining.

    Original CARL had FRESH/MODERATE/DEPLETED/CRITICAL brackets
    with different rule sets per bracket.
    """
    name: str
    threshold_pct: float   # context % where this bracket activates
    constraints: list[str] = field(default_factory=list)


DEFAULT_BRACKETS = [
    ContextBracket("fresh", 0.60, [
        "Full context available. Load all applicable domain rules.",
    ]),
    ContextBracket("moderate", 0.40, [
        "Context budget moderate. Load essential rules only, skip advisory.",
    ]),
    ContextBracket("depleted", 0.25, [
        "Context depleted. Load CRITICAL and HIGH priority rules only.",
        "Compact responses. Skip examples and verbose explanations.",
    ]),
    ContextBracket("critical", 0.10, [
        "Context critical. SAFETY rules only. Suggest /clear or subagent delegation.",
    ]),
]


# ---------------------------------------------------------------------------
# Contract match result
# ---------------------------------------------------------------------------

@dataclass
class ContractMatch:
    """Result of matching a task against available contracts."""
    contract: BehavioralContract
    matched_keywords: list[str]
    excluded: bool = False
    confidence: float = 0.0


# ---------------------------------------------------------------------------
# Contract registry (full governance engine)
# ---------------------------------------------------------------------------

class ContractRegistry:
    """Full CARL governance engine.

    Manages behavioral contracts with manifest routing, skill contracts,
    hierarchical rules, safety immutability, and context brackets.
    """

    def __init__(self) -> None:
        self._contracts: list[BehavioralContract] = []
        self._brackets: list[ContextBracket] = list(DEFAULT_BRACKETS)

    def register(self, contract: BehavioralContract) -> None:
        """Add a contract. CRITICAL contracts cannot be replaced."""
        # Check constitution: no overriding CRITICAL rules
        for existing in self._contracts:
            if (existing.name == contract.name
                    and existing.priority == Priority.CRITICAL
                    and contract.priority != Priority.CRITICAL):
                return  # silently refuse — CONSTITUTION rule 2
        # Remove existing with same name (replacement)
        self._contracts = [c for c in self._contracts if c.name != contract.name]
        self._contracts.append(contract)

    def register_many(self, contracts: list[BehavioralContract]) -> None:
        for c in contracts:
            self.register(c)

    def match(self, task: str, domain: str | None = None,
              context_pct: float = 1.0) -> list[ContractMatch]:
        """Match task against contracts with full manifest routing.

        Args:
            task: User's task description.
            domain: Optional domain filter.
            context_pct: Context budget remaining (0.0-1.0) for bracket filtering.
        """
        task_lower = task.lower()
        matches: list[ContractMatch] = []

        # Determine active context bracket
        active_bracket = self._get_bracket(context_pct)
        min_priority = self._bracket_min_priority(active_bracket)

        for contract in self._contracts:
            # Skip dormant contracts
            if contract.state == ContractState.DORMANT:
                continue

            # Domain filter
            if domain and contract.domain and contract.domain != domain:
                continue

            # Priority filter based on context bracket
            if self._priority_rank(contract.priority) < min_priority:
                continue

            # ALWAYS_ON contracts match without keywords
            if contract.load_mode == LoadMode.ALWAYS_ON:
                matches.append(ContractMatch(
                    contract=contract, matched_keywords=["ALWAYS_ON"],
                    confidence=1.0,
                ))
                continue

            # Check EXCLUDE first
            excluded_kw = [
                kw for kw in contract.exclude_keywords
                if kw.lower() in task_lower
            ]
            if excluded_kw:
                matches.append(ContractMatch(
                    contract=contract, matched_keywords=excluded_kw,
                    excluded=True, confidence=0.0,
                ))
                continue

            # RECALL keyword matching
            matched_kw = [
                kw for kw in contract.trigger_keywords
                if kw.lower() in task_lower
            ]
            if matched_kw:
                confidence = len(matched_kw) / len(contract.trigger_keywords) if contract.trigger_keywords else 0.0
                matches.append(ContractMatch(
                    contract=contract, matched_keywords=matched_kw,
                    confidence=round(confidence, 4),
                ))

        active = [m for m in matches if not m.excluded]
        active.sort(key=lambda m: (
            -self._priority_rank(m.contract.priority),
            -m.confidence,
        ))
        return active

    def get_constraints(self, task: str, domain: str | None = None,
                        context_pct: float = 1.0) -> list[str]:
        """Get all applicable constraints, respecting priority and brackets."""
        matches = self.match(task, domain, context_pct)
        constraints: list[str] = []
        for m in matches:
            constraints.extend(m.contract.constraints)
        return constraints

    def get_context_files(self, task: str, domain: str | None = None) -> list[str]:
        """Get context files from matching contracts, deduplicated."""
        matches = self.match(task, domain)
        files: list[str] = []
        seen: set[str] = set()
        for m in matches:
            for f in m.contract.context_files:
                if f not in seen:
                    files.append(f)
                    seen.add(f)
        return files

    def get_skill_deps(self, task: str, domain: str | None = None) -> dict[str, list[str]]:
        """Get aggregated READS/WRITES/REQUIRES from matching contracts."""
        matches = self.match(task, domain)
        reads: list[str] = []
        writes: list[str] = []
        requires: list[str] = []
        for m in matches:
            reads.extend(m.contract.skill.reads)
            writes.extend(m.contract.skill.writes)
            requires.extend(m.contract.skill.requires)
        return {
            "reads": sorted(set(reads)),
            "writes": sorted(set(writes)),
            "requires": sorted(set(requires)),
        }

    def check_preconditions(self, task: str, satisfied: set[str],
                            domain: str | None = None) -> list[str]:
        """Check which REQUIRES preconditions are NOT satisfied.

        Returns list of unmet precondition strings.
        """
        deps = self.get_skill_deps(task, domain)
        return [r for r in deps["requires"] if r not in satisfied]

    def get_always_on(self) -> list[BehavioralContract]:
        """Return all ALWAYS_ON contracts (loaded every session)."""
        return [c for c in self._contracts
                if c.load_mode == LoadMode.ALWAYS_ON
                and c.state == ContractState.ACTIVE]

    def get_safety_rules(self) -> list[BehavioralContract]:
        """Return all CRITICAL priority contracts (immutable safety rules)."""
        return [c for c in self._contracts if c.priority == Priority.CRITICAL]

    @property
    def contracts(self) -> list[BehavioralContract]:
        return list(self._contracts)

    @property
    def domains(self) -> set[str]:
        return {c.domain for c in self._contracts if c.domain}

    def stats(self) -> dict[str, Any]:
        return {
            "total_contracts": len(self._contracts),
            "domains": sorted(self.domains),
            "always_on": len(self.get_always_on()),
            "safety_rules": len(self.get_safety_rules()),
            "total_constraints": sum(len(c.constraints) for c in self._contracts),
            "total_context_files": sum(len(c.context_files) for c in self._contracts),
            "by_priority": {
                p.value: sum(1 for c in self._contracts if c.priority == p)
                for p in Priority
            },
            "by_state": {
                s.value: sum(1 for c in self._contracts if c.state == s)
                for s in ContractState
            },
        }

    # --- Internal helpers ---

    def _get_bracket(self, context_pct: float) -> ContextBracket | None:
        for bracket in sorted(self._brackets, key=lambda b: b.threshold_pct):
            if context_pct <= bracket.threshold_pct:
                return bracket
        return None

    @staticmethod
    def _bracket_min_priority(bracket: ContextBracket | None) -> int:
        """Return minimum priority rank allowed by this bracket."""
        if bracket is None:
            return 0  # no bracket = load everything
        if bracket.name == "critical":
            return 3  # CRITICAL only
        if bracket.name == "depleted":
            return 2  # HIGH + CRITICAL
        return 0  # fresh/moderate = load all

    @staticmethod
    def _priority_rank(p: Priority) -> int:
        return {"low": 0, "normal": 1, "high": 2, "critical": 3}.get(p.value, 1)


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_constraints(constraints: list[str]) -> str:
    """Format constraints for prompt injection."""
    if not constraints:
        return ""
    lines = ["## Behavioral Contracts (auto-applied)"]
    for i, c in enumerate(constraints, 1):
        lines.append(f"{i}. {c}")
    return "\n".join(lines)


def format_constitution() -> str:
    """Format CARL constitution rules."""
    lines = ["## CARL Constitution (meta-governance)"]
    for i, rule in enumerate(CONSTITUTION, 1):
        lines.append(f"C{i}. {rule}")
    return "\n".join(lines)
