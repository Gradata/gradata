"""Install Manifest — modular component registry with selective install.
``InstallManifest.default().plan_install(profile=...)`` returns a plan
(lite/standard/full or individual); ``Module`` carries cost + stability.
``apply(plan)`` → ``InstallState`` persistable via ``.save()``.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

__all__ = [
    "DEFAULT_MODULES",
    "DEFAULT_PROFILES",
    "InstallManifest",
    "InstallPlan",
    "InstallState",
    "Module",
    "ModuleCost",
    "ModuleStability",
    "Profile",
]


class ModuleCost(Enum):
    """Resource cost tag for modules."""

    LIGHT = "light"  # Minimal resource usage
    MEDIUM = "medium"  # Moderate resource usage
    HEAVY = "heavy"  # Significant resource usage


class ModuleStability(Enum):
    """Stability tag for modules."""

    STABLE = "stable"  # Production-ready
    BETA = "beta"  # Functional but evolving
    EXPERIMENTAL = "experimental"  # Use with caution


@dataclass
class Module:
    """A single installable module.

    Attributes:
        id: Unique module identifier.
        name: Human-readable name.
        description: What this module provides.
        kind: Module type (pattern, enhancement, integration).
        components: List of component paths this module provides.
        dependencies: Module IDs this module depends on.
        cost: Resource cost tag.
        stability: Stability tag.
        default_install: Whether to include in default installs.
    """

    id: str
    name: str
    description: str = ""
    kind: str = "enhancement"
    components: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    cost: ModuleCost = ModuleCost.LIGHT
    stability: ModuleStability = ModuleStability.STABLE
    default_install: bool = False


@dataclass
class Profile:
    """A named install profile that selects modules.

    Attributes:
        name: Profile identifier (e.g. "lite", "standard", "full").
        description: What this profile is for.
        modules: Module IDs included in this profile.
    """

    name: str
    description: str = ""
    modules: list[str] = field(default_factory=list)


@dataclass
class InstallPlan:
    """A plan for what to install/activate.

    Attributes:
        profile: The profile used (if any).
        modules: Resolved list of modules to install.
        dependencies_added: Modules added automatically via dependencies.
        estimated_cost: Aggregate cost estimate.
    """

    profile: str = ""
    modules: list[Module] = field(default_factory=list)
    dependencies_added: list[str] = field(default_factory=list)
    estimated_cost: str = "light"

    @property
    def module_ids(self) -> list[str]:
        return [m.id for m in self.modules]


@dataclass
class InstallState:
    """Persisted state of what's currently installed.

    Enables idempotent installs — only apply changes since last install.
    """

    schema_version: int = 1
    installed_modules: list[str] = field(default_factory=list)
    profile: str = ""
    install_timestamp: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def save(self, filepath: Path | str) -> None:
        """Save install state to JSON file."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def load(cls, filepath: Path | str) -> InstallState:
        """Load install state from JSON file."""
        filepath = Path(filepath)
        if not filepath.exists():
            return cls()
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def is_installed(self, module_id: str) -> bool:
        """Check if a module is currently installed."""
        # Backward compat: "carl" was renamed to "behavioral-engine"
        if module_id == "carl":
            module_id = "behavioral-engine"
        return module_id in self.installed_modules


# ---------------------------------------------------------------------------
# Default modules and profiles
# ---------------------------------------------------------------------------

DEFAULT_MODULES: list[Module] = [
    Module(
        id="core-patterns",
        name="Core Agentic Patterns",
        description="15 base agentic patterns (pipeline, RAG, reflection, etc.)",
        kind="pattern",
        components=[
            "patterns.pipeline",
            "patterns.rag",
            "patterns.reflection",
            "patterns.orchestrator",
            "patterns.parallel",
            "patterns.memory",
            "patterns.guardrails",
            "patterns.human_loop",
            "patterns.scope",
            "patterns.sub_agents",
            "patterns.evaluator",
            "patterns.tools",
        ],
        cost=ModuleCost.LIGHT,
        stability=ModuleStability.STABLE,
        default_install=True,
    ),
    Module(
        id="context-management",
        name="Context Management",
        description="Context brackets, reconciliation, task escalation, execute/qualify loop.",
        kind="pattern",
        components=[
            "patterns.context_brackets",
            "patterns.reconciliation",
            "patterns.execute_qualify",
        ],
        cost=ModuleCost.LIGHT,
        stability=ModuleStability.STABLE,
        default_install=True,
    ),
    Module(
        id="quality-gates",
        name="Quality Gates",
        description="8.0 threshold system with fix cycling and rubric evaluation.",
        kind="enhancement",
        components=["enhancements.quality_gates"],
        cost=ModuleCost.LIGHT,
        stability=ModuleStability.STABLE,
        default_install=True,
    ),
    Module(
        id="learning-pipeline",
        name="Learning Pipeline",
        description="INSTINCT->PATTERN->RULE graduation with severity-weighted confidence.",
        kind="enhancement",
        components=[
            "enhancements.self_improvement",
            "enhancements.correction_tracking",
            "enhancements.edit_classifier",
            "enhancements.pattern_extractor",
        ],
        dependencies=["quality-gates"],
        cost=ModuleCost.MEDIUM,
        stability=ModuleStability.STABLE,
        default_install=True,
    ),
    Module(
        id="behavioral-engine",
        name="Behavioral Engine",
        description="Domain-specific behavioral directives with MUST/SHOULD/MAY tiers.",
        kind="enhancement",
        components=["enhancements.behavioral_engine"],
        cost=ModuleCost.LIGHT,
        stability=ModuleStability.STABLE,
        default_install=True,
    ),
    Module(
        id="truth-protocol",
        name="Truth Protocol",
        description="Evidence-based output validation.",
        kind="enhancement",
        components=["enhancements.truth_protocol"],
        cost=ModuleCost.LIGHT,
        stability=ModuleStability.STABLE,
        default_install=True,
    ),
    Module(
        id="observation-hooks",
        name="Observation Hooks",
        description="100% deterministic tool-use observation capture for learning pipeline.",
        kind="enhancement",
        components=["enhancements.observation_hooks"],
        dependencies=["learning-pipeline"],
        cost=ModuleCost.MEDIUM,
        stability=ModuleStability.BETA,
        default_install=False,
    ),
    Module(
        id="q-learning-router",
        name="Q-Learning Agent Router",
        description="RL-based task-to-agent routing with correction-driven rewards.",
        kind="pattern",
        components=["patterns.q_learning_router"],
        dependencies=["core-patterns"],
        cost=ModuleCost.MEDIUM,
        stability=ModuleStability.BETA,
        default_install=False,
    ),
    Module(
        id="meta-rules",
        name="Meta-Rule Engine",
        description="Emergent meta-rule discovery from 3+ graduated rules.",
        kind="enhancement",
        components=["enhancements.meta_rules"],
        dependencies=["learning-pipeline"],
        cost=ModuleCost.HEAVY,
        stability=ModuleStability.BETA,
        default_install=False,
    ),
    Module(
        id="rule-integrity",
        name="Rule Integrity",
        description="HMAC signing, contradiction detection, rule verification.",
        kind="enhancement",
        components=[
            "enhancements.rule_integrity",
            "enhancements.contradiction_detector",
            "enhancements.rule_conflicts",
            "enhancements.rule_canary",
        ],
        dependencies=["learning-pipeline"],
        cost=ModuleCost.MEDIUM,
        stability=ModuleStability.STABLE,
        default_install=False,
    ),
    Module(
        id="agent-modes",
        name="Agent Operating Modes",
        description="GODMODE/PLAN/AUDIT/CANARY/SAFE switchable modes.",
        kind="pattern",
        components=["patterns.agent_modes"],
        cost=ModuleCost.LIGHT,
        stability=ModuleStability.STABLE,
        default_install=True,
    ),
    Module(
        id="integrations",
        name="LLM Integrations",
        description="Adapters for Anthropic, OpenAI, LangChain, CrewAI.",
        kind="integration",
        components=[
            "integrations.anthropic_adapter",
            "integrations.openai_adapter",
            "integrations.langchain_adapter",
            "integrations.crewai_adapter",
        ],
        cost=ModuleCost.LIGHT,
        stability=ModuleStability.STABLE,
        default_install=False,
    ),
]

DEFAULT_PROFILES: list[Profile] = [
    Profile(
        name="lite",
        description="Minimal install. Core patterns + quality gates only.",
        modules=["core-patterns", "quality-gates", "agent-modes"],
    ),
    Profile(
        name="standard",
        description="Recommended. Core + learning pipeline + behavioral engine + context management.",
        modules=[
            "core-patterns",
            "context-management",
            "quality-gates",
            "learning-pipeline",
            "behavioral-engine",
            "truth-protocol",
            "agent-modes",
        ],
    ),
    Profile(
        name="full",
        description="Everything. All modules including experimental.",
        modules=[m.id for m in DEFAULT_MODULES],
    ),
    Profile(
        name="research",
        description="Full pipeline + RL router + observation hooks for research.",
        modules=[
            "core-patterns",
            "context-management",
            "quality-gates",
            "learning-pipeline",
            "behavioral-engine",
            "truth-protocol",
            "agent-modes",
            "observation-hooks",
            "q-learning-router",
            "meta-rules",
            "rule-integrity",
        ],
    ),
]


# ---------------------------------------------------------------------------
# InstallManifest
# ---------------------------------------------------------------------------


class InstallManifest:
    """Registry of modules and profiles for selective installation.

    Handles dependency resolution, profile-based selection, and
    idempotent install state tracking.
    """

    def __init__(
        self,
        modules: list[Module] | None = None,
        profiles: list[Profile] | None = None,
    ) -> None:
        self._modules: dict[str, Module] = {}
        self._profiles: dict[str, Profile] = {}

        for m in modules or []:
            self._modules[m.id] = m
        for p in profiles or []:
            self._profiles[p.name] = p

    @classmethod
    def default(cls) -> InstallManifest:
        """Create a manifest with default modules and profiles."""
        return cls(modules=DEFAULT_MODULES, profiles=DEFAULT_PROFILES)

    @property
    def available_modules(self) -> list[Module]:
        """Return all registered modules."""
        return list(self._modules.values())

    @property
    def available_profiles(self) -> list[Profile]:
        """Return all registered profiles."""
        return list(self._profiles.values())

    def resolve_dependencies(self, module_ids: list[str]) -> list[str]:
        """Resolve module dependencies, returning full list with deps.

        Performs topological ordering to ensure dependencies come first.

        Args:
            module_ids: Initial list of module IDs.

        Returns:
            Ordered list of module IDs including all dependencies.

        Raises:
            ValueError: If a module ID is not found.
        """
        resolved: list[str] = []
        seen: set[str] = set()
        visiting: set[str] = set()  # Detect circular deps

        def _resolve(mid: str) -> None:
            # Backward compat: "carl" was renamed to "behavioral-engine"
            if mid == "carl":
                mid = "behavioral-engine"
            if mid in seen:
                return
            if mid in visiting:
                raise ValueError(
                    f"Circular dependency detected: {mid} is already in the resolution chain"
                )
            visiting.add(mid)
            module = self._modules.get(mid)
            if module is None:
                raise ValueError(f"Unknown module: {mid}")
            for dep in module.dependencies:
                _resolve(dep)
            visiting.discard(mid)
            seen.add(mid)
            resolved.append(mid)

        for mid in module_ids:
            _resolve(mid)

        return resolved

    def plan_install(
        self,
        profile: str | None = None,
        modules: list[str] | None = None,
        include: list[str] | None = None,
        exclude: list[str] | None = None,
    ) -> InstallPlan:
        """Create an install plan from a profile and/or module list.

        Args:
            profile: Profile name to use as base.
            modules: Explicit module IDs (overrides profile).
            include: Additional modules to add.
            exclude: Modules to remove.

        Returns:
            An InstallPlan with resolved modules and metadata.

        Raises:
            ValueError: If profile or module ID not found.
        """
        # Start with profile modules or explicit list
        if modules:
            selected = list(modules)
        elif profile:
            p = self._profiles.get(profile)
            if p is None:
                raise ValueError(f"Unknown profile: {profile}")
            selected = list(p.modules)
        else:
            selected = [m.id for m in self._modules.values() if m.default_install]

        # Apply include/exclude
        if include:
            selected.extend(include)
        if exclude:
            selected = [m for m in selected if m not in exclude]

        # Resolve dependencies
        original_set = set(selected)
        resolved = self.resolve_dependencies(selected)
        deps_added = [m for m in resolved if m not in original_set]

        # Build module list
        resolved_modules = [self._modules[mid] for mid in resolved]

        # Estimate aggregate cost
        costs = [m.cost for m in resolved_modules]
        if any(c == ModuleCost.HEAVY for c in costs):
            est_cost = "heavy"
        elif any(c == ModuleCost.MEDIUM for c in costs):
            est_cost = "medium"
        else:
            est_cost = "light"

        return InstallPlan(
            profile=profile or "",
            modules=resolved_modules,
            dependencies_added=deps_added,
            estimated_cost=est_cost,
        )

    def apply(
        self,
        plan: InstallPlan,
        current_state: InstallState | None = None,
    ) -> InstallState:
        """Apply an install plan and return updated state.

        This is a logical operation — actual module loading is handled
        by the caller. This method tracks what's installed.

        Args:
            plan: The install plan to apply.
            current_state: Current install state (for diff-based updates).

        Returns:
            Updated InstallState.
        """
        import time

        state = current_state or InstallState()
        state.installed_modules = plan.module_ids
        state.profile = plan.profile
        state.install_timestamp = time.time()

        return state

    def diff(
        self,
        plan: InstallPlan,
        current_state: InstallState,
    ) -> dict[str, list[str]]:
        """Compute diff between plan and current state.

        Returns:
            Dict with "add" (new modules), "remove" (removed modules),
            and "keep" (unchanged modules).
        """
        current = set(current_state.installed_modules)
        planned = set(plan.module_ids)

        return {
            "add": sorted(planned - current),
            "remove": sorted(current - planned),
            "keep": sorted(current & planned),
        }
