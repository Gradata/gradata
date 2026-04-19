"""Rule-based importance scoring for corrections before graduation. Filters noise from
INSTINCT→PATTERN→RULE by deciding if a correction is high-value (heuristics, no LLM)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

__all__ = [
    "DiscriminatorConfig",
    "DiscriminatorVerdict",
    "ImportanceSignal",
    "LessonDiscriminator",
]


class ImportanceSignal(Enum):
    """Signals that indicate a lesson's importance."""

    SEVERITY = "severity"  # High edit distance
    RECURRENCE = "recurrence"  # Seen multiple times
    DOMAIN_BREADTH = "domain_breadth"  # Applies across task types
    USER_EXPLICIT = "user_explicit"  # User explicitly flagged
    NOVELTY = "novelty"  # Not covered by existing rules
    CORRECTION_CHAIN = "correction_chain"  # Part of a correction sequence


@dataclass
class DiscriminatorConfig:
    """Configuration for the lesson discriminator.

    Attributes:
        min_confidence: Minimum confidence threshold (EverOS default: 0.6).
        severity_weights: Importance weight per severity level.
        recurrence_bonus: Confidence bonus per occurrence beyond first.
        max_recurrence_bonus: Cap on recurrence bonus.
        novelty_bonus: Bonus for lessons not covered by existing rules.
        explicit_bonus: Bonus for user-flagged corrections.
    """

    min_confidence: float = 0.6
    severity_weights: dict[str, float] = field(
        default_factory=lambda: {
            "trivial": 0.15,
            "minor": 0.35,
            "moderate": 0.55,
            "major": 0.75,
            "rewrite": 0.90,
        }
    )
    recurrence_bonus: float = 0.10
    max_recurrence_bonus: float = 0.30
    novelty_bonus: float = 0.15
    explicit_bonus: float = 0.25


@dataclass
class DiscriminatorVerdict:
    """Result of importance evaluation.

    Attributes:
        is_high_value: Whether this lesson passes the threshold.
        confidence: Confidence score (0.0-1.0).
        reasons: Human-readable reasons for the verdict.
        signals: Which importance signals fired.
        recommendation: Suggested action (graduate/monitor/discard).
    """

    is_high_value: bool
    confidence: float
    reasons: list[str] = field(default_factory=list)
    signals: list[ImportanceSignal] = field(default_factory=list)
    recommendation: str = ""

    @property
    def signal_count(self) -> int:
        return len(self.signals)


class LessonDiscriminator:
    """Evaluates whether a correction is worth graduating.

    Adapted from EverOS's ValueDiscriminator. Uses multi-signal
    heuristics instead of LLM calls:

    1. Severity scoring (higher severity = more important)
    2. Recurrence detection (seen before = pattern, not noise)
    3. Domain breadth (applies across task types = more valuable)
    4. User explicit flag (user said "remember this" = automatic high-value)
    5. Novelty check (not covered by existing rules = new knowledge)
    6. Correction chain (part of a sequence = systematic issue)

    Confidence is the sum of activated signal weights, clamped to [0, 1].
    """

    def __init__(self, config: DiscriminatorConfig | None = None) -> None:
        self.config = config or DiscriminatorConfig()

    def evaluate(
        self,
        correction_text: str = "",
        severity: str = "minor",
        task_type: str = "",
        occurrence_count: int = 1,
        is_user_explicit: bool = False,
        existing_rule_ids: list[str] | None = None,
        related_corrections: list[str] | None = None,
        affected_task_types: list[str] | None = None,
    ) -> DiscriminatorVerdict:
        """Evaluate a correction's importance for graduation.

        Args:
            correction_text: Description of the correction.
            severity: Edit distance severity level.
            task_type: Task type where correction occurred.
            occurrence_count: How many times this pattern has been seen.
            is_user_explicit: Whether the user explicitly flagged this.
            existing_rule_ids: IDs of rules that already cover this area.
            related_corrections: Other corrections in the same chain.
            affected_task_types: Task types this correction applies to.

        Returns:
            DiscriminatorVerdict with importance assessment.
        """
        confidence = 0.0
        reasons: list[str] = []
        signals: list[ImportanceSignal] = []
        existing_rule_ids = existing_rule_ids or []
        related_corrections = related_corrections or []
        affected_task_types = affected_task_types or ([task_type] if task_type else [])

        # Signal 1: Severity
        severity_weight = self.config.severity_weights.get(severity, 0.35)
        confidence += severity_weight
        if severity in ("major", "rewrite"):
            signals.append(ImportanceSignal.SEVERITY)
            reasons.append(f"High severity ({severity})")

        # Signal 2: Recurrence
        if occurrence_count > 1:
            bonus = min(
                (occurrence_count - 1) * self.config.recurrence_bonus,
                self.config.max_recurrence_bonus,
            )
            confidence += bonus
            signals.append(ImportanceSignal.RECURRENCE)
            reasons.append(f"Recurring pattern ({occurrence_count}x)")

        # Signal 3: Domain breadth
        if len(affected_task_types) > 1:
            breadth_bonus = min(0.20, len(affected_task_types) * 0.05)
            confidence += breadth_bonus
            signals.append(ImportanceSignal.DOMAIN_BREADTH)
            reasons.append(f"Applies across {len(affected_task_types)} task types")

        # Signal 4: User explicit
        if is_user_explicit:
            confidence += self.config.explicit_bonus
            signals.append(ImportanceSignal.USER_EXPLICIT)
            reasons.append("User explicitly flagged")

        # Signal 5: Novelty
        if not existing_rule_ids:
            confidence += self.config.novelty_bonus
            signals.append(ImportanceSignal.NOVELTY)
            reasons.append("Novel pattern (no existing rules)")

        # Signal 6: Correction chain
        if len(related_corrections) >= 2:
            chain_bonus = min(0.15, len(related_corrections) * 0.05)
            confidence += chain_bonus
            signals.append(ImportanceSignal.CORRECTION_CHAIN)
            reasons.append(f"Part of correction chain ({len(related_corrections)} related)")

        # Clamp confidence
        confidence = round(min(1.0, max(0.0, confidence)), 4)

        # Apply threshold
        is_high_value = confidence >= self.config.min_confidence

        # Determine recommendation
        if is_high_value and confidence >= 0.8:
            recommendation = "graduate"
        elif is_high_value or confidence >= 0.4:
            recommendation = "monitor"
        else:
            recommendation = "discard"

        if not reasons:
            reasons.append(f"Low confidence ({confidence:.2f})")

        return DiscriminatorVerdict(
            is_high_value=is_high_value,
            confidence=confidence,
            reasons=reasons,
            signals=signals,
            recommendation=recommendation,
        )

    def batch_evaluate(
        self,
        corrections: list[dict],
    ) -> list[DiscriminatorVerdict]:
        """Evaluate multiple corrections at once.

        Args:
            corrections: List of dicts with keys matching evaluate() params.

        Returns:
            List of DiscriminatorVerdict, one per correction.
        """
        return [self.evaluate(**c) for c in corrections]

    def filter_high_value(
        self,
        corrections: list[dict],
    ) -> list[tuple[dict, DiscriminatorVerdict]]:
        """Filter corrections to only high-value ones.

        Returns:
            List of (correction_dict, verdict) tuples for high-value items.
        """
        results = []
        for correction in corrections:
            verdict = self.evaluate(**correction)
            if verdict.is_high_value:
                results.append((correction, verdict))
        return results
