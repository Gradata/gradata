"""RuleContext — Central hub for graduated rules consumed by all patterns.

This is the ONE mechanism that connects the graduation pipeline to the 22
pattern modules. Graduation publishes rules here. Patterns query from here.
The cycle: corrections → graduation → rules → patterns improve → fewer corrections.

Lives in patterns/ (Layer 0) so all patterns can import without circular deps.
Does NOT import from enhancements/ — graduation pushes data IN via the bridge.

Usage:
    # Any pattern can query:
    from gradata.rules.rule_context import get_rule_context
    ctx = get_rule_context()
    tone_rules = ctx.query(category="TONE")

    # Graduation bridge publishes:
    ctx.publish(GraduatedRule(category="TONE", principle="keep it casual", ...))
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field


@dataclass(frozen=True)
class GraduatedRule:
    """A rule that has graduated through the learning pipeline."""

    rule_id: str
    category: str          # TONE, DRAFTING, SECURITY, PROCESS, etc.
    principle: str         # The rule text
    confidence: float      # 0.60+ for PATTERN, 0.90+ for RULE
    scope: dict = field(default_factory=dict)  # task_type, agent_type, audience, etc.
    source_type: str = "lesson"  # "lesson", "meta_rule", "distilled"
    tags: tuple[str, ...] = ()   # Freeform tags for pattern matching
    agent_type: str = ""         # Scoped to specific agent (empty = universal)

    @property
    def is_rule_tier(self) -> bool:
        return self.confidence >= 0.90

    @property
    def is_pattern_tier(self) -> bool:
        return 0.60 <= self.confidence < 0.90


def _rule_matches_domain(rule: GraduatedRule, domain_norm: str) -> bool:
    """Return True if ``rule`` is in-scope for ``domain_norm`` (already lowercased).

    STRICT matching (council verdict 4/4). Match rules (OR):
      1. ``rule.scope["domain"]`` equals ``domain_norm`` (case-insensitive).
      2. ``rule.scope["applies_to"]`` equals ``domain_norm`` or starts with
         ``f"{domain_norm}:"``.

    ``rule.category`` is deliberately ignored. Categories are taxonomy
    labels (STYLE, TONE, SECURITY), not domains. Legacy rules with no
    ``scope.domain`` set must be migrated via
    ``scripts/migrate_legacy_scopes.py``.
    """
    if not domain_norm:
        return True
    scope = rule.scope or {}
    if str(scope.get("domain", "")).strip().lower() == domain_norm:
        return True
    applies = str(scope.get("applies_to", "")).strip().lower()
    if applies == domain_norm:
        return True
    return bool(applies) and applies.startswith(f"{domain_norm}:")


class RuleContext:
    """Singleton registry of graduated rules that all patterns query.

    Populated by the graduation bridge at session start and on graduation events.
    Queried by patterns to adapt their behavior based on learned rules.
    """

    def __init__(self) -> None:
        self._rules: dict[str, GraduatedRule] = {}
        self._by_category: dict[str, list[str]] = defaultdict(list)
        self._by_agent: dict[str, list[str]] = defaultdict(list)
        self._by_tag: dict[str, list[str]] = defaultdict(list)

    def publish(self, rule: GraduatedRule) -> None:
        """Add or update a graduated rule. Called by the bridge."""
        if rule.rule_id in self._rules:
            # Remove old index entries before re-adding
            old = self._rules[rule.rule_id]
            cat_list = self._by_category.get(old.category, [])
            if old.rule_id in cat_list:
                cat_list.remove(old.rule_id)
            if old.agent_type:
                agent_list = self._by_agent.get(old.agent_type, [])
                if old.rule_id in agent_list:
                    agent_list.remove(old.rule_id)
            for tag in old.tags:
                tag_list = self._by_tag.get(tag, [])
                if old.rule_id in tag_list:
                    tag_list.remove(old.rule_id)
        self._rules[rule.rule_id] = rule
        self._by_category[rule.category].append(rule.rule_id)
        if rule.agent_type:
            self._by_agent[rule.agent_type].append(rule.rule_id)
        for tag in rule.tags:
            self._by_tag[tag].append(rule.rule_id)

    def query(
        self,
        category: str = "",
        tags: list[str] | None = None,
        agent_type: str = "",
        min_confidence: float = 0.0,
        limit: int = 10,
        domain: str | None = None,
    ) -> list[GraduatedRule]:
        """Query graduated rules. Any pattern can call this.

        Args:
            domain: Optional domain filter. When set, only rules whose
                ``scope["domain"]`` matches (case-insensitive) or whose
                ``scope["applies_to"]`` equals ``domain`` or starts with
                ``f"{domain}:"`` are returned. Category is NOT used as a
                fallback (council verdict 4/4 STRICT).
        """
        candidates = list(self._rules.values())

        if category:
            cat_ids = set(self._by_category.get(category.upper(), []))
            candidates = [r for r in candidates if r.rule_id in cat_ids]

        if agent_type:
            agent_ids = set(self._by_agent.get(agent_type, []))
            # Include universal rules (no agent scope) + agent-specific
            candidates = [r for r in candidates if not r.agent_type or r.rule_id in agent_ids]

        if tags:
            tag_ids: set[str] = set()
            for tag in tags:
                tag_ids.update(self._by_tag.get(tag, []))
            candidates = [r for r in candidates if r.rule_id in tag_ids]

        if domain:
            d_norm = domain.strip().lower()
            candidates = [r for r in candidates if _rule_matches_domain(r, d_norm)]

        if min_confidence > 0:
            candidates = [r for r in candidates if r.confidence >= min_confidence]

        # Sort by confidence descending (highest confidence first)
        candidates.sort(key=lambda r: r.confidence, reverse=True)
        return candidates[:limit]

    # ── Pattern-specific query helpers ──────────────────────────────

    def for_reflection(self, task_type: str = "") -> list[GraduatedRule]:
        """Rules that should become reflection/critique criteria."""
        rules = self.query(min_confidence=0.60, limit=20)
        if task_type:
            # Prefer rules scoped to this task type
            scoped = [r for r in rules if r.scope.get("task_type") == task_type]
            universal = [r for r in rules if not r.scope.get("task_type")]
            return (scoped + universal)[:10]
        return rules[:10]

    def for_guardrails(self) -> list[GraduatedRule]:
        """Rules that should become guardrail checks (SECURITY, ACCURACY, SAFETY)."""
        guard_categories = {"SECURITY", "ACCURACY", "SAFETY", "HONESTY", "DATA_INTEGRITY"}
        return [r for r in self.query(min_confidence=0.60, limit=20)
                if r.category in guard_categories]

    def for_evaluator(self, task_type: str = "") -> list[GraduatedRule]:
        """Rules that should become evaluation dimensions (DRAFTING, STYLE, FORMAT)."""
        eval_categories = {"DRAFTING", "STYLE", "FORMAT", "TONE", "CONTENT", "STRUCTURE"}
        rules = [r for r in self.query(min_confidence=0.60, limit=20)
                 if r.category in eval_categories]
        if task_type:
            scoped = [r for r in rules if r.scope.get("task_type") == task_type]
            universal = [r for r in rules if not r.scope.get("task_type")]
            return (scoped + universal)[:10]
        return rules[:10]


    def for_agent(self, agent_type: str) -> list[GraduatedRule]:
        """Rules scoped to a specific agent type."""
        return self.query(agent_type=agent_type, min_confidence=0.60, limit=10)

    def rules_budget(self, bracket: str = "FRESH") -> int:
        """Max rules to inject based on context degradation bracket."""
        budgets = {"FRESH": 10, "MODERATE": 5, "DEEP": 2, "CRITICAL": 0}
        return budgets.get(bracket, 10)

    def correction_density(self, category: str) -> float:
        """Ratio of rules in a category to total rules. High = many corrections."""
        total = len(self._rules)
        if total == 0:
            return 0.0
        cat_count = len(self._by_category.get(category.upper(), []))
        return cat_count / total

    def stats(self) -> dict:
        """Summary for logging and diagnostics."""
        rules = list(self._rules.values())
        return {
            "total_rules": len(rules),
            "rule_tier": sum(1 for r in rules if r.is_rule_tier),
            "pattern_tier": sum(1 for r in rules if r.is_pattern_tier),
            "categories": dict(sorted(
                {k: len(v) for k, v in self._by_category.items()}.items(),
                key=lambda x: x[1], reverse=True
            )),
            "agents": list(self._by_agent.keys()),
        }

    def clear(self) -> None:
        """Reset all rules. Used in testing."""
        self._rules.clear()
        self._by_category.clear()
        self._by_agent.clear()
        self._by_tag.clear()


# ── Module-level singleton ──────────────────────────────────────────

_context: RuleContext | None = None


def get_rule_context() -> RuleContext:
    """Get the global RuleContext singleton."""
    global _context
    if _context is None:
        _context = RuleContext()
    return _context
