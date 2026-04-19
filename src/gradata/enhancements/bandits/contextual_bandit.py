"""Thompson-Sampling contextual bandit for rule selection (explore-exploit).
Each rule holds Beta(alpha=accepts, beta=rejects); posterior draws pick
top-k per context, balancing exploration of low-confidence rules with
exploitation. Context-dependent — a rule working for executives may not
for peers. Ref: Multi-Armed Bandits Meet LLMs (arXiv:2505.13355, 2025).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class RuleArm:
    """A rule's bandit statistics (Beta distribution parameters).

    Beta(alpha, beta) is the conjugate prior for Bernoulli outcomes.
    alpha = successes + 1 (prior), beta = failures + 1 (prior).
    Starting at Beta(1,1) = uniform prior (no information).
    """

    rule_id: str
    alpha: float = 1.0  # successes + prior
    beta: float = 1.0  # failures + prior
    total_pulls: int = 0
    context_scores: dict[str, float] = field(default_factory=dict)

    @property
    def expected_value(self) -> float:
        """Mean of the Beta distribution = alpha / (alpha + beta)."""
        return self.alpha / (self.alpha + self.beta)

    def sample(self) -> float:
        """Draw from Beta(alpha, beta) for Thompson Sampling."""
        return random.betavariate(self.alpha, self.beta)


@dataclass
class SelectionResult:
    """Result of bandit-based rule selection."""

    selected_rules: list[str]  # Rule IDs selected
    scores: dict[str, float]  # Rule ID -> Thompson sample score
    was_exploration: dict[str, bool]  # Rule ID -> True if selected via exploration


class RuleBandit:
    """Contextual bandit for rule application using Thompson Sampling."""

    def __init__(self, exploration_bonus: float = 0.1) -> None:
        self._arms: dict[str, RuleArm] = {}
        self._exploration_bonus = exploration_bonus

    def get_or_create_arm(self, rule_id: str) -> RuleArm:
        """Get or create a bandit arm for a rule."""
        if rule_id not in self._arms:
            self._arms[rule_id] = RuleArm(rule_id=rule_id)
        return self._arms[rule_id]

    def update(self, rule_id: str, accepted: bool, context_key: str = "") -> None:
        """Update a rule's arm based on application outcome.

        Args:
            rule_id: The rule that was applied.
            accepted: True if the rule's application was accepted/helpful.
            context_key: Optional context key for context-dependent learning
                        (e.g., "email_draft:executive").
        """
        arm = self.get_or_create_arm(rule_id)
        arm.total_pulls += 1

        if accepted:
            arm.alpha += 1.0
        else:
            arm.beta += 1.0

        # Track context-specific performance
        if context_key:
            if context_key not in arm.context_scores:
                arm.context_scores[context_key] = 0.5
            # Exponential moving average
            current = arm.context_scores[context_key]
            arm.context_scores[context_key] = round(
                0.8 * current + 0.2 * (1.0 if accepted else 0.0), 4
            )

    def select(
        self,
        candidates: list[str],
        context: dict | None = None,
        k: int = 5,
    ) -> SelectionResult:
        """Select top-k rules using Thompson Sampling.

        Args:
            candidates: List of rule IDs eligible for this context.
            context: Optional context dict for context-dependent scoring.
            k: Number of rules to select.

        Returns:
            SelectionResult with selected rules and their scores.
        """
        context_key = self._build_context_key(context) if context else ""

        scores: dict[str, float] = {}
        for rule_id in candidates:
            arm = self.get_or_create_arm(rule_id)
            base_score = arm.sample()

            # Context boost: if this rule has a good track record in this context
            if context_key and context_key in arm.context_scores:
                context_score = arm.context_scores[context_key]
                base_score = 0.7 * base_score + 0.3 * context_score

            # Exploration bonus for under-sampled rules
            if arm.total_pulls < 5:
                base_score += self._exploration_bonus

            scores[rule_id] = round(base_score, 4)

        # Select top-k
        ranked = sorted(scores.keys(), key=lambda r: scores[r], reverse=True)
        selected = ranked[:k]

        # Determine which selections were exploration.
        # Exploration = Thompson sample exceeded expected value significantly,
        # meaning a low-EV arm got lucky and was picked over higher-EV arms.
        was_exploration: dict[str, bool] = {}
        for rule_id in selected:
            arm = self.get_or_create_arm(rule_id)
            # A rule with few pulls that scored high is exploration
            was_exploration[rule_id] = arm.total_pulls < 5 or (
                scores[rule_id] > arm.expected_value * 1.3
            )

        return SelectionResult(
            selected_rules=selected,
            scores={r: scores[r] for r in selected},
            was_exploration=was_exploration,
        )

    def _build_context_key(self, context: dict) -> str:
        """Build a hashable context key from a context dict."""
        parts = []
        for key in sorted(["task", "audience", "domain"]):
            if key in context:
                parts.append(f"{key}:{context[key]}")
        return "|".join(parts) if parts else ""

    def export_arms(self) -> list[dict]:
        """Export all arm data for DB persistence."""
        return [
            {
                "rule_id": arm.rule_id,
                "alpha": arm.alpha,
                "beta": arm.beta,
                "total_pulls": arm.total_pulls,
                "context_scores": arm.context_scores,
            }
            for arm in self._arms.values()
        ]

    def load_arms(self, data: list[dict]) -> None:
        """Load arm data from DB."""
        for d in data:
            arm = RuleArm(
                rule_id=d["rule_id"],
                alpha=d.get("alpha", 1.0),
                beta=d.get("beta", 1.0),
                total_pulls=d.get("total_pulls", 0),
                context_scores=d.get("context_scores", {}),
            )
            self._arms[arm.rule_id] = arm
