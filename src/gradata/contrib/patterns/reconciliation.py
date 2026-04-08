"""
Reconciliation — Mandatory plan-vs-actual comparison (UNIFY).
=============================================================
Adapted from: paul (ChristopherKahler/paul) unify-phase.md

Enforces mandatory reconciliation after every execution phase.
Compares planned outcomes against actual results, scores deviations,
and produces structured summaries.

Usage::

    from gradata.contrib.patterns.reconciliation import (
        Reconciler, PlanItem, ActualResult,
        DeviationScore, ReconciliationSummary,
    )

    plan = [
        PlanItem(id="AC-1", description="User can log in", criteria="200 OK on /login"),
        PlanItem(id="AC-2", description="Token stored", criteria="JWT in localStorage"),
    ]
    actuals = [
        ActualResult(plan_id="AC-1", achieved=True, evidence="curl returns 200"),
        ActualResult(plan_id="AC-2", achieved=False, evidence="Token in cookie, not localStorage"),
    ]
    summary = Reconciler().reconcile(plan, actuals)
    print(summary.overall_score)  # DeviationScore.GAP
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

__all__ = [
    "ActualResult",
    "DeviationDetail",
    "DeviationScore",
    "PlanItem",
    "Reconciler",
    "ReconciliationSummary",
    "format_summary",
]


class DeviationScore(Enum):
    """Qualification score for plan-vs-actual comparison."""
    PASS = "pass"       # Actual matches plan exactly
    GAP = "gap"         # Partial achievement, missing elements
    DRIFT = "drift"     # Achieved something different than planned


@dataclass
class PlanItem:
    """A single planned outcome with acceptance criteria.

    Attributes:
        id: Unique identifier (e.g. "AC-1", "TASK-3").
        description: What was planned.
        criteria: How to verify achievement (executable check preferred).
        files: Optional list of files expected to be modified.
    """
    id: str
    description: str
    criteria: str = ""
    files: list[str] = field(default_factory=list)


@dataclass
class ActualResult:
    """The actual outcome for a planned item.

    Attributes:
        plan_id: References the PlanItem.id this result corresponds to.
        achieved: Whether the planned outcome was fully achieved.
        evidence: Proof of achievement or explanation of gap.
        deviation: Description of how actual differed from plan (if any).
        files_modified: Actual files that were modified.
    """
    plan_id: str
    achieved: bool
    evidence: str = ""
    deviation: str = ""
    files_modified: list[str] = field(default_factory=list)


@dataclass
class DeviationDetail:
    """Detailed deviation analysis for a single plan item.

    Attributes:
        plan_id: The plan item identifier.
        score: PASS, GAP, or DRIFT.
        what_differed: Description of the deviation.
        why: Root cause analysis.
        impact: How the deviation affects the overall goal.
        classification: Root cause type (intent/spec/code).
    """
    plan_id: str
    score: DeviationScore
    what_differed: str = ""
    why: str = ""
    impact: str = ""
    classification: str = ""  # "intent", "spec", or "code"


@dataclass
class ReconciliationSummary:
    """Full reconciliation output from a UNIFY pass.

    Attributes:
        plan_items: The original plan items.
        actual_results: The actual results achieved.
        deviations: Detailed deviation analysis per item.
        overall_score: Aggregate qualification (worst-of-all deviations).
        pass_count: Number of items that passed.
        gap_count: Number of items with gaps.
        drift_count: Number of items that drifted.
        unmatched_plans: Plan IDs with no corresponding actual result.
        extra_results: Actual results with no corresponding plan item.
        decisions: Key decisions made during execution.
        metadata: Arbitrary metadata from the reconciliation.
    """
    plan_items: list[PlanItem]
    actual_results: list[ActualResult]
    deviations: list[DeviationDetail]
    overall_score: DeviationScore
    pass_count: int = 0
    gap_count: int = 0
    drift_count: int = 0
    unmatched_plans: list[str] = field(default_factory=list)
    extra_results: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def fully_passed(self) -> bool:
        """True if all plan items passed with no gaps or drift."""
        return self.overall_score == DeviationScore.PASS and not self.unmatched_plans

    @property
    def completion_ratio(self) -> float:
        """Fraction of plan items that fully passed."""
        total = len(self.plan_items)
        if total == 0:
            return 1.0
        return self.pass_count / total


class Reconciler:
    """Performs mandatory plan-vs-actual reconciliation.

    The reconciler compares each plan item against its actual result,
    scores deviations, and produces a structured summary. Items without
    matching results are flagged as unmatched.
    """

    def reconcile(
        self,
        plan: list[PlanItem],
        actuals: list[ActualResult],
        decisions: list[str] | None = None,
    ) -> ReconciliationSummary:
        """Compare plan against actuals and produce a reconciliation summary.

        Args:
            plan: The planned items with acceptance criteria.
            actuals: The actual results achieved during execution.
            decisions: Optional list of key decisions made during execution.

        Returns:
            A ReconciliationSummary with deviation analysis and scores.
        """
        actual_map: dict[str, ActualResult] = {a.plan_id: a for a in actuals}
        # Deduplicate plan items by ID (first occurrence wins)
        seen_plan_ids: set[str] = set()
        unique_plan: list[PlanItem] = []
        for p in plan:
            if p.id not in seen_plan_ids:
                seen_plan_ids.add(p.id)
                unique_plan.append(p)
        plan = unique_plan
        plan_ids = {p.id for p in plan}
        actual_ids = {a.plan_id for a in actuals}

        deviations: list[DeviationDetail] = []
        pass_count = 0
        gap_count = 0
        drift_count = 0

        for item in plan:
            actual = actual_map.get(item.id)
            if actual is None:
                deviations.append(DeviationDetail(
                    plan_id=item.id,
                    score=DeviationScore.GAP,
                    what_differed="No result provided for this plan item.",
                    impact="Plan item was not addressed.",
                ))
                gap_count += 1
                continue

            deviation = self._score_deviation(item, actual)
            deviations.append(deviation)

            if deviation.score == DeviationScore.PASS:
                pass_count += 1
            elif deviation.score == DeviationScore.GAP:
                gap_count += 1
            else:
                drift_count += 1

        # Determine overall score (worst-of-all)
        if drift_count > 0:
            overall = DeviationScore.DRIFT
        elif gap_count > 0:
            overall = DeviationScore.GAP
        else:
            overall = DeviationScore.PASS

        unmatched = sorted(plan_ids - actual_ids)
        extra = sorted(actual_ids - plan_ids)

        return ReconciliationSummary(
            plan_items=plan,
            actual_results=actuals,
            deviations=deviations,
            overall_score=overall,
            pass_count=pass_count,
            gap_count=gap_count,
            drift_count=drift_count,
            unmatched_plans=unmatched,
            extra_results=extra,
            decisions=decisions or [],
        )

    def _score_deviation(
        self,
        plan: PlanItem,
        actual: ActualResult,
    ) -> DeviationDetail:
        """Score a single plan-item against its actual result.

        Logic:
            - achieved=True and no deviation text → PASS
            - achieved=True but deviation text present → DRIFT
            - achieved=False → GAP
        """
        if actual.achieved and not actual.deviation:
            return DeviationDetail(
                plan_id=plan.id,
                score=DeviationScore.PASS,
            )

        if actual.achieved and actual.deviation:
            return DeviationDetail(
                plan_id=plan.id,
                score=DeviationScore.DRIFT,
                what_differed=actual.deviation,
                impact="Achieved differently than planned.",
                classification=self._classify_root_cause(plan, actual),
            )

        return DeviationDetail(
            plan_id=plan.id,
            score=DeviationScore.GAP,
            what_differed=actual.deviation or "Not achieved.",
            why=actual.evidence,
            impact="Plan item incomplete.",
            classification=self._classify_root_cause(plan, actual),
        )

    def _classify_root_cause(
        self,
        plan: PlanItem,
        actual: ActualResult,
    ) -> str:
        """Classify the root cause of a deviation.

        Three categories (from paul diagnostic-failure-routing):
            - intent: The plan's goal was wrong (replan needed)
            - spec: The acceptance criteria were wrong (fix plan first)
            - code: Implementation didn't match correct plan (fix code)
        """
        evidence_lower = actual.evidence.lower()
        deviation_lower = actual.deviation.lower()
        combined = evidence_lower + " " + deviation_lower

        # Heuristic classification
        intent_signals = ("wrong approach", "should not have", "requirements changed",
                         "misunderstood", "wrong goal", "different requirement")
        spec_signals = ("criteria wrong", "spec incorrect", "acceptance criteria",
                       "test was wrong", "wrong assertion", "bad criteria")

        if any(s in combined for s in intent_signals):
            return "intent"
        if any(s in combined for s in spec_signals):
            return "spec"
        return "code"


def format_summary(summary: ReconciliationSummary) -> str:
    """Format a reconciliation summary as human-readable text.

    Args:
        summary: The reconciliation summary to format.

    Returns:
        Multi-line formatted string.
    """
    lines = [
        "## Reconciliation Summary (UNIFY)",
        f"Overall: **{summary.overall_score.value.upper()}** "
        f"({summary.pass_count}P / {summary.gap_count}G / {summary.drift_count}D)",
        f"Completion: {summary.completion_ratio:.0%}",
        "",
    ]

    if summary.deviations:
        lines.append("### Deviations")
        for dev in summary.deviations:
            status = dev.score.value.upper()
            lines.append(f"- **{dev.plan_id}**: {status}")
            if dev.what_differed:
                lines.append(f"  What: {dev.what_differed}")
            if dev.classification:
                lines.append(f"  Root cause: {dev.classification}")
        lines.append("")

    if summary.unmatched_plans:
        lines.append(f"### Unmatched Plans: {', '.join(summary.unmatched_plans)}")
    if summary.extra_results:
        lines.append(f"### Extra Results: {', '.join(summary.extra_results)}")

    if summary.decisions:
        lines.append("### Decisions")
        for d in summary.decisions:
            lines.append(f"- {d}")

    return "\n".join(lines)