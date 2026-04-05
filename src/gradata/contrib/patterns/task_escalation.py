"""
Task Escalation — Four-status execution outcome system.
========================================================
Adapted from: paul (ChristopherKahler/paul) loop-phases.md

Replaces binary pass/fail with four nuanced statuses:
DONE, DONE_WITH_CONCERNS, NEEDS_CONTEXT, BLOCKED.

Prevents silent uncertainty by making "I finished but I'm not sure"
an explicit, first-class outcome.

Usage::

    from gradata.contrib.patterns.task_escalation import (
        TaskStatus, TaskOutcome, report_outcome,
        is_actionable, requires_human,
    )

    outcome = report_outcome(
        status=TaskStatus.DONE_WITH_CONCERNS,
        description="Implemented auth endpoint",
        concerns=["JWT expiry not tested with edge cases"],
    )
    assert requires_human(outcome)  # True — concerns need review
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

__all__ = [
    "TaskStatus",
    "TaskOutcome",
    "report_outcome",
    "is_actionable",
    "requires_human",
    "format_outcome",
]


class TaskStatus(Enum):
    """Four-level task execution outcome.

    DONE: Task completed successfully, no concerns.
    DONE_WITH_CONCERNS: Completed but agent has doubts. Prevents
        silent uncertainty — the critical middle status.
    NEEDS_CONTEXT: Cannot complete — missing information. Pauses
        execution and surfaces what's needed.
    BLOCKED: Cannot complete — structural impediment. Stops
        execution and reports what blocks progress.
    """
    DONE = "done"
    DONE_WITH_CONCERNS = "done_with_concerns"
    NEEDS_CONTEXT = "needs_context"
    BLOCKED = "blocked"


@dataclass
class TaskOutcome:
    """Structured outcome from task execution.

    Attributes:
        status: The four-level status.
        task_id: Optional identifier for the task.
        description: What was done (or attempted).
        concerns: Doubts or quality issues (for DONE_WITH_CONCERNS).
        missing_context: What information is needed (for NEEDS_CONTEXT).
        blockers: What prevents progress (for BLOCKED).
        evidence: Proof of completion or explanation of failure.
        files_modified: Files changed during execution.
        metadata: Arbitrary metadata.
    """
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

    Validates that the appropriate fields are populated for each status:
    - DONE_WITH_CONCERNS requires at least one concern
    - NEEDS_CONTEXT requires at least one missing_context item
    - BLOCKED requires at least one blocker

    Args:
        status: The task execution status.
        description: What was done or attempted.
        task_id: Optional task identifier.
        concerns: Quality doubts (required for DONE_WITH_CONCERNS).
        missing_context: What's needed (required for NEEDS_CONTEXT).
        blockers: What's blocking (required for BLOCKED).
        evidence: Proof or explanation.
        files_modified: List of modified files.

    Returns:
        A validated TaskOutcome.

    Raises:
        ValueError: If required fields for the status are missing.
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
    """Whether the outcome allows continuing to the next task.

    Only DONE and DONE_WITH_CONCERNS are actionable.
    NEEDS_CONTEXT and BLOCKED require intervention before proceeding.
    """
    return outcome.status in (TaskStatus.DONE, TaskStatus.DONE_WITH_CONCERNS)


def requires_human(outcome: TaskOutcome) -> bool:
    """Whether the outcome requires human attention.

    DONE_WITH_CONCERNS, NEEDS_CONTEXT, and BLOCKED all require review.
    Only DONE proceeds without human intervention.
    """
    return outcome.status != TaskStatus.DONE


def format_outcome(outcome: TaskOutcome) -> str:
    """Format a task outcome as a structured text block.

    Returns a multi-line string suitable for reporting or logging.
    """
    status_emoji = {
        TaskStatus.DONE: "PASS",
        TaskStatus.DONE_WITH_CONCERNS: "WARN",
        TaskStatus.NEEDS_CONTEXT: "PAUSE",
        TaskStatus.BLOCKED: "STOP",
    }

    lines = [
        f"[{status_emoji[outcome.status]}] {outcome.status.value}",
    ]

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
