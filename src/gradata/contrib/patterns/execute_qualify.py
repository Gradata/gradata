"""
Execute/Qualify — Fresh verification loop with diagnostic routing.
==================================================================
Adapted from: paul (ChristopherKahler/paul) checkpoints.md, apply-phase.md

Enforces a disciplined execute-then-verify loop:
1. Execute the task
2. Report status (DONE/DONE_WITH_CONCERNS/NEEDS_CONTEXT/BLOCKED)
3. Qualify: re-read output files fresh, run verification, compare to spec
4. Score: PASS/GAP/DRIFT
5. On failure: classify root cause (intent/spec/code) and retry (max 3)

The key insight: never trust memory. Always re-read files after execution.

Usage::

    from gradata.contrib.patterns.execute_qualify import (
        ExecuteQualifyLoop, QualifyResult, FailureClassification,
    )

    loop = ExecuteQualifyLoop(max_attempts=3)
    result = loop.run(
        executor=my_executor,
        qualifier=my_qualifier,
        task_spec="Implement login endpoint",
    )
    print(result.passed)        # True/False
    print(result.attempts_used) # 1-3
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

__all__ = [
    "ExecuteQualifyLoop",
    "ExecuteQualifyResult",
    "ExecutorFn",
    "FailureClassification",
    "FixerFn",
    "QualifierFn",
    "QualifyResult",
    "QualifyScore",
    "TaskOutcome",
    "TaskStatus",
    "format_outcome",
    "is_actionable",
    "report_outcome",
    "requires_human",
]


class TaskStatus(Enum):
    """Four-level task execution outcome."""
    DONE = "done"
    DONE_WITH_CONCERNS = "done_with_concerns"
    NEEDS_CONTEXT = "needs_context"
    BLOCKED = "blocked"


@dataclass
class TaskOutcome:
    """Structured outcome from task execution."""
    status: TaskStatus
    task_id: str = ""
    description: str = ""
    concerns: list[str] = field(default_factory=list)
    missing_context: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    evidence: str = ""
    files_modified: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def report_outcome(
    status: TaskStatus,
    description: str = "",
    task_id: str = "",
    concerns: list[str] | None = None,
    missing_context: list[str] | None = None,
    blockers: list[str] | None = None,
    evidence: str = "",
    files_modified: list[str] | None = None,
) -> TaskOutcome:
    """Create a structured task outcome with validation.

    DONE_WITH_CONCERNS requires concerns; NEEDS_CONTEXT requires missing_context;
    BLOCKED requires blockers.
    """
    concerns = concerns or []
    missing_context = missing_context or []
    blockers = blockers or []
    files_modified = files_modified or []

    if status == TaskStatus.DONE_WITH_CONCERNS and not concerns:
        raise ValueError(
            "DONE_WITH_CONCERNS requires at least one concern. "
            "Use DONE if there are no concerns."
        )
    if status == TaskStatus.NEEDS_CONTEXT and not missing_context:
        raise ValueError(
            "NEEDS_CONTEXT requires at least one missing_context item. "
            "Specify what information is needed."
        )
    if status == TaskStatus.BLOCKED and not blockers:
        raise ValueError(
            "BLOCKED requires at least one blocker. "
            "Specify what prevents progress."
        )

    return TaskOutcome(
        status=status,
        task_id=task_id,
        description=description,
        concerns=concerns,
        missing_context=missing_context,
        blockers=blockers,
        evidence=evidence,
        files_modified=files_modified,
    )


def is_actionable(outcome: TaskOutcome) -> bool:
    """Only DONE and DONE_WITH_CONCERNS allow continuing."""
    return outcome.status in (TaskStatus.DONE, TaskStatus.DONE_WITH_CONCERNS)


def requires_human(outcome: TaskOutcome) -> bool:
    """Everything except DONE needs human review."""
    return outcome.status != TaskStatus.DONE


def format_outcome(outcome: TaskOutcome) -> str:
    """Format a task outcome as a structured text block."""
    status_emoji = {
        TaskStatus.DONE: "PASS",
        TaskStatus.DONE_WITH_CONCERNS: "WARN",
        TaskStatus.NEEDS_CONTEXT: "PAUSE",
        TaskStatus.BLOCKED: "STOP",
    }
    lines = [f"[{status_emoji[outcome.status]}] {outcome.status.value}"]
    if outcome.task_id:
        lines.append(f"  Task: {outcome.task_id}")
    if outcome.description:
        lines.append(f"  What: {outcome.description}")
    if outcome.concerns:
        lines.append("  Concerns:")
        for c in outcome.concerns:
            lines.append(f"    - {c}")
    if outcome.missing_context:
        lines.append("  Missing context:")
        for m in outcome.missing_context:
            lines.append(f"    - {m}")
    if outcome.blockers:
        lines.append("  Blockers:")
        for b in outcome.blockers:
            lines.append(f"    - {b}")
    if outcome.evidence:
        lines.append(f"  Evidence: {outcome.evidence}")
    return "\n".join(lines)


class QualifyScore(Enum):
    """Qualification score from fresh verification."""
    PASS = "pass"
    GAP = "gap"
    DRIFT = "drift"


class FailureClassification(Enum):
    """Root cause classification for qualification failures.

    Determines the correct fix strategy:
    - INTENT: The plan's goal was wrong. Replan with updated intent.
    - SPEC: The acceptance criteria were wrong. Fix plan first, then code.
    - CODE: Implementation doesn't match correct plan. Fix code in place.
    """
    INTENT = "intent"
    SPEC = "spec"
    CODE = "code"


@dataclass
class QualifyResult:
    """Result from a single qualify pass.

    Attributes:
        score: PASS, GAP, or DRIFT.
        evidence: Proof of verification.
        classification: Root cause if score != PASS.
        concerns: Issues found during qualification.
    """
    score: QualifyScore
    evidence: str = ""
    classification: FailureClassification | None = None
    concerns: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.score == QualifyScore.PASS


@dataclass
class ExecuteQualifyResult:
    """Aggregate result from the full execute/qualify loop.

    Attributes:
        passed: Whether the task ultimately passed qualification.
        attempts_used: How many execute+qualify cycles were run.
        max_attempts: The ceiling configured on the loop.
        final_outcome: The last TaskOutcome from execution.
        final_qualify: The last QualifyResult from verification.
        attempt_history: Full history of (outcome, qualify) pairs.
    """
    passed: bool
    attempts_used: int
    max_attempts: int
    final_outcome: TaskOutcome | None = None
    final_qualify: QualifyResult | None = None
    attempt_history: list[tuple[TaskOutcome, QualifyResult | None]] = field(
        default_factory=list
    )


# Type aliases for callables
ExecutorFn = Callable[[str, int], TaskOutcome]
QualifierFn = Callable[[TaskOutcome, str], QualifyResult]
FixerFn = Callable[[TaskOutcome, QualifyResult, int], None]


class ExecuteQualifyLoop:
    """Disciplined execute-then-verify loop with diagnostic routing.

    The loop enforces:
    1. Execute the task
    2. If NEEDS_CONTEXT or BLOCKED, stop immediately
    3. Qualify: fresh verification against spec
    4. If PASS, done
    5. If GAP/DRIFT, classify root cause and retry (up to max_attempts)

    Args:
        max_attempts: Maximum number of execute+qualify cycles (default 3).
    """

    def __init__(self, max_attempts: int = 3) -> None:
        if max_attempts < 1:
            raise ValueError(f"max_attempts must be >= 1, got {max_attempts}")
        self.max_attempts = max_attempts

    def run(
        self,
        executor: ExecutorFn,
        qualifier: QualifierFn,
        task_spec: str,
        fixer: FixerFn | None = None,
    ) -> ExecuteQualifyResult:
        """Run the full execute/qualify loop.

        Args:
            executor: Callable ``(task_spec, attempt) -> TaskOutcome``.
                Executes the task and returns a structured outcome.
            qualifier: Callable ``(outcome, task_spec) -> QualifyResult``.
                Verifies the outcome by re-reading files and running checks.
                Must perform fresh reads, never trust memory.
            task_spec: The task specification/acceptance criteria.
            fixer: Optional callable ``(outcome, qualify_result, attempt) -> None``.
                Called between attempts when qualification fails. Should
                apply fixes based on the failure classification.

        Returns:
            An ExecuteQualifyResult with the full attempt history.
        """
        history: list[tuple[TaskOutcome, QualifyResult | None]] = []

        for attempt in range(1, self.max_attempts + 1):
            # Step 1: Execute
            outcome = executor(task_spec, attempt)

            # Step 2: Check if execution itself failed
            if outcome.status in (TaskStatus.NEEDS_CONTEXT, TaskStatus.BLOCKED):
                history.append((outcome, None))
                return ExecuteQualifyResult(
                    passed=False,
                    attempts_used=attempt,
                    max_attempts=self.max_attempts,
                    final_outcome=outcome,
                    final_qualify=None,
                    attempt_history=history,
                )

            # Step 3: Qualify — fresh verification
            qualify = qualifier(outcome, task_spec)
            history.append((outcome, qualify))

            # Step 4: Check qualification
            if qualify.passed:
                return ExecuteQualifyResult(
                    passed=True,
                    attempts_used=attempt,
                    max_attempts=self.max_attempts,
                    final_outcome=outcome,
                    final_qualify=qualify,
                    attempt_history=history,
                )

            # Step 5: If not last attempt, apply fix
            if attempt < self.max_attempts and fixer is not None:
                fixer(outcome, qualify, attempt)

        # Exhausted all attempts
        last_outcome, last_qualify = history[-1]
        return ExecuteQualifyResult(
            passed=False,
            attempts_used=self.max_attempts,
            max_attempts=self.max_attempts,
            final_outcome=last_outcome,
            final_qualify=last_qualify,
            attempt_history=history,
        )
