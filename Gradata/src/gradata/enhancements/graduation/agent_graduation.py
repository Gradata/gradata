"""
Agent Graduation — Compounding Behavioral Adaptation for Agents & Subagents
============================================================================
Layer 1 Enhancement: imports from patterns/ (sub_agents, human_loop, memory)

Applies the same INSTINCT→PATTERN→RULE graduation pipeline to agent outputs,
creating trained agents that compound over time. Three mechanisms:

1. **Agent-level graduation**: Each agent type accumulates behavioral lessons
   from orchestrator feedback (approve/edit/reject). Lessons graduate the
   same way user corrections do — through confidence scoring and maturity.

2. **Human approval graduation**: The approval gate ITSELF graduates.
   Early sessions require manual review. As an agent proves reliable (high
   FDA), the gate loosens from CONFIRM → PREVIEW → AUTO. New agent types
   always start at CONFIRM.

3. **Upward distillation**: Agent learnings that prove valuable (PATTERN+)
   are distilled upward to the brain level, enriching the main lessons store.
   Cross-agent patterns (discovered by one agent, useful to others) propagate
   through the brain layer.

Usage:
    tracker = AgentGraduationTracker(brain_dir)

    # Record agent output quality
    tracker.record_outcome("research", output, "approved", edits=None)
    tracker.record_outcome("writer", output, "edited", edits="rewrote intro")

    # Check if an agent needs human approval
    gate = tracker.approval_gate("research")  # "auto" | "preview" | "confirm"

    # Get agent's graduated lessons for prompt injection
    rules = tracker.get_agent_rules("research")

    # Distill proven agent lessons up to brain level
    distilled = tracker.distill_upward()

Research backing:
    - Same constants as user-level graduation (Brown et al. 2024, NIST Bayesian)
    - Human-in-the-loop graduation mirrors trust calibration literature
      (Lee & See 2004, "Trust in Automation")
    - Hierarchical RL option discovery parallels (Sutton et al. 1999)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

# Import graduation constants from self_improvement (same research-backed values)
from gradata.enhancements.self_improvement import (
    ACCEPTANCE_BONUS,
    MIN_APPLICATIONS_FOR_PATTERN,
    MIN_APPLICATIONS_FOR_RULE,
    MISFIRE_PENALTY,
    PATTERN_THRESHOLD,
    RULE_THRESHOLD,
    SURVIVAL_BONUS,
    Lesson,
    LessonState,
    format_lessons,
    get_maturity_phase,
    parse_lessons,
)

# ---------------------------------------------------------------------------
# Approval Gate Thresholds
# ---------------------------------------------------------------------------
# These define when an agent's approval gate graduates.
# FDA = First-Draft Acceptance (output used without edits)

GATE_CONFIRM_TO_PREVIEW = 0.70  # 70% FDA over 10+ outputs → PREVIEW
GATE_PREVIEW_TO_AUTO = 0.90  # 90% FDA over 25+ outputs → AUTO
GATE_MIN_OUTPUTS_PREVIEW = 10  # Minimum outputs before PREVIEW eligible
GATE_MIN_OUTPUTS_AUTO = 25  # Minimum outputs before AUTO eligible
GATE_DEMOTION_THRESHOLD = 3  # 3 consecutive rejections → demote gate


@dataclass
class AgentProfile:
    """Behavioral profile for a specific agent type.

    Tracks the agent's quality history and graduated lessons.
    Each agent type (research, writer, critic, etc.) has its own profile.
    """

    agent_type: str
    total_outputs: int = 0
    approved_unchanged: int = 0  # FDA — used without edits
    approved_edited: int = 0  # Approved but the user made changes
    rejected: int = 0  # Output rejected/redone
    consecutive_rejections: int = 0
    approval_gate: str = "confirm"  # "confirm" | "preview" | "auto"
    lessons: list[Lesson] = field(default_factory=list)
    created_at: str = ""
    last_updated: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = _now()
        self.last_updated = _now()

    @property
    def fda_rate(self) -> float:
        """First-draft acceptance rate (approved unchanged / total)."""
        if self.total_outputs == 0:
            return 0.0
        return self.approved_unchanged / self.total_outputs

    @property
    def acceptance_rate(self) -> float:
        """Overall acceptance rate (approved + edited / total)."""
        if self.total_outputs == 0:
            return 0.0
        return (self.approved_unchanged + self.approved_edited) / self.total_outputs

    @property
    def maturity_phase(self) -> str:
        """Agent's maturity based on total outputs (not sessions)."""
        return get_maturity_phase(self.total_outputs)


@dataclass
class AgentOutcome:
    """Record of a single agent output evaluation."""

    agent_type: str
    outcome: str  # "approved" | "edited" | "rejected"
    edits: str | None  # What was changed (if edited)
    output_preview: str  # First 200 chars of agent output
    session: int = 0
    timestamp: str = ""
    patterns_extracted: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = _now()


@dataclass
class DeterministicRule:
    """A graduated RULE compiled into an enforceable check function.

    Unlike prompt-injected rules (soft guidance), deterministic rules
    run as actual code — regex patterns, keyword blocklists, data validators.
    They produce pass/fail results, not LLM-interpreted suggestions.

    Attributes:
        name: Rule identifier (from lesson category + description hash)
        category: Lesson category (CONSTRAINT, POSITIONING, etc.)
        description: Human-readable rule text
        pattern: Compiled regex pattern (if regex-enforceable)
        check_fn: Callable that takes output text and returns check result
        enforcement: "block" (prevent output) or "warn" (flag but allow)
    """

    name: str
    category: str
    description: str
    pattern: re.Pattern | None = None
    enforcement: str = "block"

    def check(self, output: str) -> dict:
        """Run the deterministic check against output text.

        Returns:
            {"passed": bool, "detail": str}
        """
        if self.pattern:
            match = self.pattern.search(output)
            if match:
                return {
                    "passed": False,
                    "detail": f"Pattern matched: '{match.group(0)[:50]}'",
                }
            return {"passed": True, "detail": "No violations found"}
        return {"passed": True, "detail": "No check pattern defined"}


@dataclass
class EnforcementResult:
    """Result of applying deterministic rules to agent output."""

    passed: bool
    violations: list[dict]
    rules_checked: int


# ---------------------------------------------------------------------------
# Enforceable Category Patterns
# ---------------------------------------------------------------------------
# These map lesson categories to regex patterns that can enforce the rule.
# Each entry: category -> list of (keyword_trigger, regex_pattern) pairs.
# The keyword_trigger matches in the lesson description to identify which
# pattern to compile. This is how a RULE like "Never use agency pricing"
# becomes a regex that blocks "agency pricing" in output.

_ENFORCEABLE_PATTERNS: dict[str, list[tuple[str, str]]] = {
    "POSITIONING": [
        ("agency pricing", r"(?i)\bagency\s+pricing\b"),
        ("expensive retainer", r"(?i)\bexpensive\s+retainer\b"),
        ("competitor", r"(?i)\b(?:salesforce|hubspot|marketo)\b"),
    ],
    "CONSTRAINT": [
        ("paid", r"(?i)\b(?:paid\s+tier|subscription\s+required|credit\s+card)\b"),
        (
            "cost money",
            r"(?i)\b(?:monthly\s+fee|per\s+month|/mo(?:nth)?)\b.*(?:composio|clay|phantombuster)",
        ),
    ],
    "PRICING": [
        ("starter", r"(?i)starter.*(?:multi|multiple|two|2)\s*(?:account|brand)"),
    ],
    "DATA_INTEGRITY": [
        (
            "owner_only",
            r"(?i)\b(?:EXCLUDED_NAMES_PLACEHOLDER)(?:'s)?\s+(?:campaign|deal|contact|lead)",
        ),  # configure excluded names in brain config
    ],
}


def compile_deterministic_rule(lesson: Lesson) -> DeterministicRule | None:
    """Attempt to compile a RULE-tier lesson into a deterministic guard.

    Looks up the lesson's category in _ENFORCEABLE_PATTERNS, then checks
    if the lesson description matches any keyword trigger. If so, compiles
    the associated regex pattern.

    Returns None if the lesson can't be deterministically enforced
    (e.g., DRAFTING rules that require LLM judgment).
    """
    if lesson.state != LessonState.RULE:
        return None

    category = lesson.category.upper()
    patterns = _ENFORCEABLE_PATTERNS.get(category, [])

    desc_lower = lesson.description.lower()
    for keyword, regex in patterns:
        if keyword.lower() in desc_lower:
            return DeterministicRule(
                name=f"{category}:{keyword[:20]}",
                category=category,
                description=lesson.description,
                pattern=re.compile(regex),
                enforcement="block",
            )

    return None


def _now() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# Agent Graduation Tracker
# ---------------------------------------------------------------------------


class AgentGraduationTracker:
    """Manages graduation pipelines for all agent types in a brain.

    Directory structure:
        brain/
          agents/
            {agent_type}/
              profile.json     — AgentProfile (quality history + gate state)
              lessons.md       — Agent-level graduated lessons
              outcomes.jsonl   — Raw outcome log (append-only)
    """

    def __init__(self, brain_dir: str | Path) -> None:
        self.brain_dir = Path(brain_dir)
        self.agents_dir = self.brain_dir / "agents"
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self._profiles: dict[str, AgentProfile] = {}

    def _agent_dir(self, agent_type: str) -> Path:
        d = self.agents_dir / agent_type
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _load_profile(self, agent_type: str) -> AgentProfile:
        """Load or create agent profile."""
        if agent_type in self._profiles:
            return self._profiles[agent_type]

        profile_path = self._agent_dir(agent_type) / "profile.json"
        if profile_path.exists():
            try:
                data = json.loads(profile_path.read_text(encoding="utf-8"))
                # Load lessons from lessons.md
                lessons_path = self._agent_dir(agent_type) / "lessons.md"
                lessons = []
                if lessons_path.exists():
                    lessons = parse_lessons(lessons_path.read_text(encoding="utf-8"))
                profile = AgentProfile(
                    agent_type=data.get("agent_type", agent_type),
                    total_outputs=data.get("total_outputs", 0),
                    approved_unchanged=data.get("approved_unchanged", 0),
                    approved_edited=data.get("approved_edited", 0),
                    rejected=data.get("rejected", 0),
                    consecutive_rejections=data.get("consecutive_rejections", 0),
                    approval_gate=data.get("approval_gate", "confirm"),
                    lessons=lessons,
                    created_at=data.get("created_at", _now()),
                )
                self._profiles[agent_type] = profile
                return profile
            except (json.JSONDecodeError, KeyError):
                pass

        profile = AgentProfile(agent_type=agent_type)
        self._profiles[agent_type] = profile
        return profile

    def _save_profile(self, profile: AgentProfile) -> None:
        """Persist agent profile to disk."""
        profile.last_updated = _now()
        profile_path = self._agent_dir(profile.agent_type) / "profile.json"
        data = {
            "agent_type": profile.agent_type,
            "total_outputs": profile.total_outputs,
            "approved_unchanged": profile.approved_unchanged,
            "approved_edited": profile.approved_edited,
            "rejected": profile.rejected,
            "consecutive_rejections": profile.consecutive_rejections,
            "approval_gate": profile.approval_gate,
            "fda_rate": round(profile.fda_rate, 3),
            "acceptance_rate": round(profile.acceptance_rate, 3),
            "maturity_phase": profile.maturity_phase,
            "lesson_count": len(profile.lessons),
            "created_at": profile.created_at,
            "last_updated": profile.last_updated,
        }
        profile_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        # Save lessons
        if profile.lessons:
            lessons_path = self._agent_dir(profile.agent_type) / "lessons.md"
            lessons_path.write_text(
                f"# Agent Lessons — {profile.agent_type}\n"
                f"# Maturity: {profile.maturity_phase} | FDA: {profile.fda_rate:.0%}\n\n"
                + format_lessons(profile.lessons),
                encoding="utf-8",
            )

    def record_outcome(
        self,
        agent_type: str,
        output_preview: str,
        outcome: str,
        edits: str | None = None,
        session: int = 0,
        patterns: list[str] | None = None,
        task_type: str = "",
        edit_category: str = "",
    ) -> AgentProfile:
        """Record an agent output evaluation and update graduation.

        Args:
            agent_type: Type of agent (e.g., "research", "writer", "critic")
            output_preview: First 200 chars of agent output
            outcome: "approved" (used as-is), "edited" (used with changes),
                     "rejected" (output discarded/redone)
            edits: Description of what was changed (if edited)
            session: Current session number
            patterns: Extracted behavioral patterns from the edit

        Returns:
            Updated AgentProfile
        """
        profile = self._load_profile(agent_type)

        # Update counters
        profile.total_outputs += 1
        if outcome == "approved":
            profile.approved_unchanged += 1
            profile.consecutive_rejections = 0
        elif outcome == "edited":
            profile.approved_edited += 1
            profile.consecutive_rejections = 0
        elif outcome == "rejected":
            profile.rejected += 1
            profile.consecutive_rejections += 1

        # Log outcome (append-only)
        outcome_record = AgentOutcome(
            agent_type=agent_type,
            outcome=outcome,
            edits=edits,
            output_preview=output_preview[:200],
            session=session,
            patterns_extracted=patterns or [],
        )
        outcomes_path = self._agent_dir(agent_type) / "outcomes.jsonl"
        with open(outcomes_path, "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "agent_type": outcome_record.agent_type,
                        "outcome": outcome_record.outcome,
                        "edits": outcome_record.edits,
                        "output_preview": outcome_record.output_preview,
                        "session": outcome_record.session,
                        "timestamp": outcome_record.timestamp,
                        "patterns_extracted": outcome_record.patterns_extracted,
                    }
                )
                + "\n"
            )

        # Extract lessons from edits (corrections feed agent graduation)
        if outcome == "edited" and edits:
            self._extract_agent_lesson(
                profile, edits, session, task_type=task_type, edit_category=edit_category
            )
        elif outcome == "rejected" and edits:
            self._extract_agent_lesson(
                profile,
                edits,
                session,
                is_rejection=True,
                task_type=task_type,
                edit_category=edit_category,
            )

        # Update approval gate graduation
        self._update_approval_gate(profile)

        # Update existing lesson confidence (survival/contradiction)
        # H2 fix: pass edit_category so fire_count is gated on category match.
        self._update_lesson_confidence(profile, outcome, session, edit_category=edit_category)

        self._save_profile(profile)
        return profile

    def _extract_agent_lesson(
        self,
        profile: AgentProfile,
        edits: str,
        session: int,
        is_rejection: bool = False,
        task_type: str = "",
        edit_category: str = "",
    ) -> None:
        """Extract a scoped behavioral lesson from an edit/rejection.

        This is the agent-level equivalent of brain.correct() — it turns
        The user's edits to agent output into graduated lessons with SCOPE.

        Scope means the lesson only applies when the agent is doing the
        same type of task. A research agent lesson scoped to "prospect_research"
        won't fire when the same agent does "competitive_analysis".

        Args:
            edit_category: Classification of the edit (tone/content/structure/
                          factual/style). From diff engine if available.
            task_type: The task type the agent was performing when corrected.
                      Used to scope the lesson.
        """
        # Build scoped category: AGENT_TYPE or AGENT_TYPE/TASK_TYPE
        category = "AGENT_" + profile.agent_type.upper()
        if edit_category:
            category = edit_category.upper()
        today = datetime.now(UTC).strftime("%Y-%m-%d")

        # Check for duplicate (same edit pattern already captured)
        edit_lower = edits.lower()[:100]
        for existing in profile.lessons:
            if existing.description and edit_lower in existing.description.lower()[:100]:
                return  # Already captured

        # Build scope JSON (empty = universal, task_type = scoped)
        scope_json = ""
        if task_type:
            scope_json = json.dumps({"task_type": task_type})

        new_lesson = Lesson(
            date=today,
            state=LessonState.INSTINCT,
            confidence=0.30 if not is_rejection else 0.40,
            category=category,
            description=edits[:300],
            fire_count=1,
            scope_json=scope_json,
        )
        profile.lessons.append(new_lesson)

    def _update_lesson_confidence(
        self,
        profile: AgentProfile,
        outcome: str,
        session: int,
        edit_category: str = "",
    ) -> None:
        """Update confidence on existing agent lessons based on outcome.

        Same mechanics as user-level graduation:
        - Approved unchanged: +0.05 (acceptance bonus)
        - Approved with edits: +0.10 (survival bonus — lesson survived)
        - Rejected: -0.25 (misfire penalty)

        H2 fix: fire_count is only incremented when the lesson's category
        matches edit_category (or when edit_category is not provided, for
        backward compatibility). This mirrors the main pipeline's
        was_injected gate and prevents approval of one category from
        boosting fire_count for unrelated lessons — which was silently
        fast-tracking promotion of lessons that never actually fired.
        """
        norm_edit_cat = edit_category.upper() if edit_category else ""
        for lesson in profile.lessons:
            if lesson.state == LessonState.UNTESTABLE:
                continue

            # Gate fire_count on category relevance: only count a fire for a
            # lesson whose category matches the corrected category. When
            # edit_category is empty (legacy callers), fall back to always
            # counting (backward compatible).
            category_matches = not norm_edit_cat or lesson.category.upper() == norm_edit_cat

            if outcome == "approved":
                lesson.confidence = min(1.0, lesson.confidence + ACCEPTANCE_BONUS)
                if category_matches:
                    lesson.fire_count += 1
            elif outcome == "edited":
                lesson.confidence = min(1.0, lesson.confidence + SURVIVAL_BONUS)
                if category_matches:
                    lesson.fire_count += 1
            elif outcome == "rejected":
                lesson.confidence = max(0.0, lesson.confidence + MISFIRE_PENALTY)

            # Check for promotion
            # H1 fix: INSTINCT->PATTERN uses strict > so a lesson born at
            # INITIAL_CONFIDENCE (0.60) == PATTERN_THRESHOLD (0.60) cannot
            # promote on the same session it was created.
            if (
                lesson.state == LessonState.INSTINCT
                and lesson.confidence > PATTERN_THRESHOLD
                and lesson.fire_count >= MIN_APPLICATIONS_FOR_PATTERN
            ):
                lesson.state = LessonState.PATTERN
            elif (
                lesson.state == LessonState.PATTERN
                and lesson.confidence >= RULE_THRESHOLD
                and lesson.fire_count >= MIN_APPLICATIONS_FOR_RULE
            ):
                lesson.state = LessonState.RULE

    def _update_approval_gate(self, profile: AgentProfile) -> None:
        """Graduate the human approval gate based on agent track record.

        Gate graduation:
          CONFIRM (always review) → PREVIEW (show summary, quick approve)
          → AUTO (auto-execute, spot-check only)

        Demotion: 3 consecutive rejections drops gate one level.
        """
        # Demotion check first
        if profile.consecutive_rejections >= GATE_DEMOTION_THRESHOLD:
            if profile.approval_gate == "auto":
                profile.approval_gate = "preview"
            elif profile.approval_gate == "preview":
                profile.approval_gate = "confirm"
            profile.consecutive_rejections = 0  # Reset after demotion
            return

        # Promotion check
        if (
            profile.approval_gate == "confirm"
            and profile.total_outputs >= GATE_MIN_OUTPUTS_PREVIEW
            and profile.fda_rate >= GATE_CONFIRM_TO_PREVIEW
        ):
            profile.approval_gate = "preview"

        if (
            profile.approval_gate == "preview"
            and profile.total_outputs >= GATE_MIN_OUTPUTS_AUTO
            and profile.fda_rate >= GATE_PREVIEW_TO_AUTO
        ):
            profile.approval_gate = "auto"

    def get_approval_gate(self, agent_type: str) -> str:
        """Get current approval gate level for an agent type.

        Returns: "confirm" | "preview" | "auto"
        """
        profile = self._load_profile(agent_type)
        return profile.approval_gate

    def get_agent_rules(self, agent_type: str, task_type: str = "") -> list[str]:
        """Get graduated PATTERN/RULE lessons for prompt injection.

        If task_type is provided, only returns lessons whose scope matches
        that task type (or lessons with no scope, which are universal).
        This is scoped rule selection — the agent-level equivalent of
        brain.apply_brain_rules() with RuleScope filtering.

        Args:
            agent_type: Agent type to get rules for
            task_type: If provided, filter to rules scoped to this task type

        Returns:
            List of formatted rule strings for prompt injection
        """
        profile = self._load_profile(agent_type)
        rules = []
        for lesson in profile.lessons:
            if lesson.state not in (LessonState.PATTERN, LessonState.RULE):
                continue

            # Scope filtering: if task_type is provided, only include
            # universal rules (no scope) or rules scoped to this task_type
            if task_type and lesson.scope_json:
                try:
                    scope = json.loads(lesson.scope_json)
                    lesson_task = scope.get("task_type", "")
                    if lesson_task and lesson_task != task_type:
                        continue  # Scoped to a different task type
                except (json.JSONDecodeError, TypeError):
                    pass  # Malformed scope = treat as universal

            scope_tag = ""
            if lesson.scope_json:
                try:
                    scope = json.loads(lesson.scope_json)
                    scope_tag = f" [scope:{scope.get('task_type', '?')}]"
                except (json.JSONDecodeError, TypeError):
                    pass

            rules.append(
                f"[{lesson.state.value}] {lesson.category}: {lesson.description}{scope_tag}"
            )
        return rules

    def get_agent_context(self, agent_type: str, task_type: str = "") -> str:
        """Get full agent context for prompt injection.

        Includes: maturity phase, FDA rate, graduated rules filtered by scope.
        This is what makes a trained agent different from a fresh one.
        """
        profile = self._load_profile(agent_type)
        rules = self.get_agent_rules(agent_type, task_type=task_type)

        if not rules:
            return ""

        lines = [
            f"# Agent Training Context ({agent_type})",
            f"# Maturity: {profile.maturity_phase} | "
            f"FDA: {profile.fda_rate:.0%} | "
            f"Gate: {profile.approval_gate}",
            "",
        ]
        lines.extend(rules)
        return "\n".join(lines)

    def distill_upward(self, min_state: LessonState = LessonState.PATTERN) -> list[dict]:
        """Distill proven agent lessons up to brain level.

        Returns lessons from all agents that have graduated to at least
        min_state (default: PATTERN). These should be added to the brain's
        main lessons.md.

        Only returns lessons not yet distilled (tracked via _distilled flag).
        """
        distilled: list[dict] = []

        for agent_dir in sorted(self.agents_dir.iterdir()):
            if not agent_dir.is_dir():
                continue
            agent_type = agent_dir.name
            profile = self._load_profile(agent_type)

            for lesson in profile.lessons:
                # Only distill lessons at or above threshold
                if lesson.state.value not in ("PATTERN", "RULE"):
                    continue
                if min_state == LessonState.RULE and lesson.state != LessonState.RULE:
                    continue

                distilled.append(
                    {
                        "agent_type": agent_type,
                        "category": lesson.category,
                        "description": lesson.description,
                        "state": lesson.state.value,
                        "confidence": lesson.confidence,
                        "fire_count": lesson.fire_count,
                        "source": f"agent:{agent_type}",
                    }
                )

        return distilled

    def get_all_profiles(self) -> list[AgentProfile]:
        """Get profiles for all agent types."""
        profiles = []
        for agent_dir in sorted(self.agents_dir.iterdir()):
            if agent_dir.is_dir() and (agent_dir / "profile.json").exists():
                profiles.append(self._load_profile(agent_dir.name))
        return profiles

    def format_dashboard(self) -> str:
        """Format a dashboard showing all agent graduation status."""
        profiles = self.get_all_profiles()
        if not profiles:
            return "No agent profiles yet."

        lines = ["# Agent Graduation Dashboard", ""]
        lines.append("| Agent | Outputs | FDA | Gate | Lessons | Maturity |")
        lines.append("|-------|---------|-----|------|---------|----------|")
        for p in profiles:
            rules = sum(1 for l in p.lessons if l.state == LessonState.RULE)
            patterns = sum(1 for l in p.lessons if l.state == LessonState.PATTERN)
            instincts = sum(1 for l in p.lessons if l.state == LessonState.INSTINCT)
            lines.append(
                f"| {p.agent_type} | {p.total_outputs} | "
                f"{p.fda_rate:.0%} | {p.approval_gate} | "
                f"{rules}R/{patterns}P/{instincts}I | {p.maturity_phase} |"
            )
        return "\n".join(lines)

    def compute_quality_scores(self) -> dict:
        """Compute per-agent quality scores from graduation profiles.

        This replaces the ``agent_quality_scores()`` function previously in
        ``brain/scripts/spawn.py`` (lines 584-687).  Instead of querying raw
        VERIFICATION events, it uses the richer graduation profiles which
        already track FDA, acceptance rate, and lesson counts.

        Returns:
            Dict matching the spawn.py ``agent_quality_scores()`` shape::

                {
                    "by_agent": {
                        "<agent_type>": {
                            "total_verified": int,
                            "pass_rate": float,
                            "avg_score": float,  # FDA as 0-10
                            "reject_count": int,
                            "common_issues": [str, ...],
                        }, ...
                    },
                    "overall_pass_rate": float,
                    "overall_avg_score": float,
                    "worst_agent": str | None,
                    "best_agent": str | None,
                }
        """
        profiles = self.get_all_profiles()
        if not profiles:
            return {
                "by_agent": {},
                "overall_pass_rate": 0,
                "overall_avg_score": 0,
                "worst_agent": None,
                "best_agent": None,
            }

        by_agent: dict[str, dict] = {}
        total_accepted = 0
        total_all = 0
        all_scores: list[float] = []

        for p in profiles:
            if p.total_outputs == 0:
                continue

            # Map FDA to a 0-10 scale for compatibility with spawn.py shape
            avg_score = round(p.fda_rate * 10, 1)
            pass_rate = round(p.acceptance_rate, 2)

            # Extract recent issues from INSTINCT-level lessons
            recent_issues = [
                lesson.description
                for lesson in reversed(p.lessons)
                if lesson.state == LessonState.INSTINCT
            ][:3]

            by_agent[p.agent_type] = {
                "total_verified": p.total_outputs,
                "pass_rate": pass_rate,
                "avg_score": avg_score,
                "reject_count": p.rejected,
                "common_issues": recent_issues,
            }

            total_accepted += p.approved_unchanged + p.approved_edited
            total_all += p.total_outputs
            all_scores.append(avg_score)

        overall_pass = round(total_accepted / total_all, 2) if total_all else 0
        overall_avg = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0

        best = None
        worst = None
        if by_agent:
            best = max(by_agent, key=lambda k: by_agent[k]["avg_score"])
            worst = min(by_agent, key=lambda k: by_agent[k]["avg_score"])

        return {
            "by_agent": by_agent,
            "overall_pass_rate": overall_pass,
            "overall_avg_score": overall_avg,
            "worst_agent": worst,
            "best_agent": best,
        }

    def get_deterministic_rules(
        self, agent_type: str, task_type: str = ""
    ) -> list[DeterministicRule]:
        """Get RULE-tier lessons compiled into enforceable guard logic.

        Only RULE-tier lessons with an enforceable pattern are returned.
        These should be applied as hard constraints on agent output,
        not just soft prompt guidance.

        Categories with natural enforcement patterns:
        - CONSTRAINT: budget/tool restrictions → check_fn blocks violations
        - DATA_INTEGRITY: owner filtering → check_fn validates data source
        - PRICING: tier accuracy → check_fn validates pricing claims
        - POSITIONING: banned phrases → check_fn blocks forbidden language

        Categories that stay as prompt guidance (not enforceable):
        - DRAFTING: style/tone → requires LLM judgment
        - COMMUNICATION: empathy/framing → requires LLM judgment
        - DEMO_PREP: research depth → requires LLM judgment

        Args:
            agent_type: Agent type to get rules for
            task_type: If provided, filter by scope

        Returns:
            List of DeterministicRule instances with compiled check functions
        """
        profile = self._load_profile(agent_type)
        rules: list[DeterministicRule] = []

        for lesson in profile.lessons:
            if lesson.state != LessonState.RULE:
                continue

            # Scope filtering
            if task_type and lesson.scope_json:
                try:
                    scope = json.loads(lesson.scope_json)
                    if scope.get("task_type", "") and scope["task_type"] != task_type:
                        continue
                except (json.JSONDecodeError, TypeError):
                    pass

            det_rule = compile_deterministic_rule(lesson)
            if det_rule is not None:
                rules.append(det_rule)

        return rules

    def enforce_rules(self, agent_type: str, output: str, task_type: str = "") -> EnforcementResult:
        """Apply all deterministic RULE-tier guards to agent output.

        Returns an EnforcementResult with pass/fail and details of any violations.
        This is the hard enforcement layer — violations are blocking.

        Args:
            agent_type: Agent type whose rules to enforce
            output: The agent's raw output text
            task_type: Task type for scoped rule filtering

        Returns:
            EnforcementResult with violations list (empty = passed)
        """
        det_rules = self.get_deterministic_rules(agent_type, task_type)
        violations: list[dict] = []

        for rule in det_rules:
            result = rule.check(output)
            if not result["passed"]:
                violations.append(
                    {
                        "rule": rule.name,
                        "category": rule.category,
                        "description": rule.description,
                        "violation": result["detail"],
                    }
                )

        return EnforcementResult(
            passed=len(violations) == 0,
            violations=violations,
            rules_checked=len(det_rules),
        )
