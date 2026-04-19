"""Risk-tiered human approval gates for agentic pipelines (stdlib-only). ``assess_risk``:
low/medium/high via keyword match. ``gate``: auto-approves low, surfaces ApprovalRequest
for medium/high. Reversibility is a first-class derived signal independent of tier."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

# ---------------------------------------------------------------------------
# Risk keyword tables
# ---------------------------------------------------------------------------

# Each keyword set maps to a tier.  Order matters: HIGH is evaluated first so
# a single action string cannot be demoted by the presence of LOW keywords.

_HIGH_RISK_KEYWORDS: frozenset[str] = frozenset(
    {
        # Destructive / irreversible
        "delete",
        "destroy",
        "remove",
        "drop",
        "purge",
        "wipe",
        "truncate",
        "overwrite",
        "reset",
        "uninstall",
        # Publish / transmit externally
        "send",
        "publish",
        "post",
        "submit",
        "broadcast",
        "deploy",
        "release",
        "push",
        "commit",
        "merge",
        "execute",
        "run",
        "trigger",
        # Permissions / credentials
        "grant",
        "revoke",
        "elevate",
        "sudo",
        "admin",
        "impersonate",
        # Financial
        "charge",
        "pay",
        "transfer",
        "withdraw",
        "invoice",
    }
)

_MEDIUM_RISK_KEYWORDS: frozenset[str] = frozenset(
    {
        # Mutations that are recoverable but consequential
        "update",
        "edit",
        "modify",
        "patch",
        "replace",
        "rename",
        "move",
        "archive",
        "disable",
        "enable",
        "toggle",
        "configure",
        "set",
        "write",
        "save",
        "upload",
        "import",
        "export",
        "schedule",
        "enqueue",
        "notify",
        "alert",
    }
)

_LOW_RISK_KEYWORDS: frozenset[str] = frozenset(
    {
        # Read-only / exploratory
        "read",
        "fetch",
        "get",
        "list",
        "search",
        "query",
        "find",
        "load",
        "inspect",
        "check",
        "validate",
        "verify",
        "preview",
        "summarize",
        "analyze",
        "analyse",
        "review",
        "draft",
        "generate",
        "suggest",
        "recommend",
        "estimate",
        "calculate",
        "compute",
        "compare",
        "log",
        "monitor",
        "observe",
    }
)

# Verbs that indicate the action is NOT easily reversible (used to set
# the ``reversible`` flag regardless of tier).
_IRREVERSIBLE_KEYWORDS: frozenset[str] = frozenset(
    {
        "delete",
        "destroy",
        "drop",
        "purge",
        "wipe",
        "truncate",
        "send",
        "publish",
        "broadcast",
        "deploy",
        "release",
        "charge",
        "pay",
        "transfer",
        "withdraw",
        "revoke",
    }
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class RiskAssessment:
    """Classification of an action's risk profile.

    Args:
        tier: Risk level — ``"low"``, ``"medium"``, or ``"high"``.
        reason: Human-readable explanation of why this tier was assigned.
        affected: List of entity names or resource identifiers that the
            action will affect (extracted from the action string or
            context dict).
        reversible: ``True`` if the action can be undone after execution.
    """

    tier: str
    reason: str
    affected: list[str] = field(default_factory=list)
    reversible: bool = True


@dataclass
class ApprovalRequest:
    """Structured request for a human reviewer to approve or reject an action.

    Args:
        action: Original action string as supplied to ``gate``.
        risk: ``RiskAssessment`` produced for this action.
        preview: Human-readable impact summary from ``preview_action``.
    """

    action: str
    risk: RiskAssessment
    preview: str


@dataclass
class ApprovalResult:
    """Outcome of a human approval decision.

    This dataclass is a value object; the *collection* of the decision
    (via CLI prompt, web form, Slack message, etc.) is the host's
    responsibility.

    Args:
        approved: ``True`` if the reviewer approved the action.
        feedback: Optional freeform comment from the reviewer.
    """

    approved: bool
    feedback: str | None = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def assess_risk(
    action: str,
    context: dict[str, Any] | None = None,
) -> RiskAssessment:
    """Classify the risk level of a proposed action.

    Risk is determined by matching action tokens against three keyword
    sets (HIGH > MEDIUM > LOW).  The first keyword set that yields a
    match wins.  If no keywords match, the action defaults to
    ``"medium"`` risk as a conservative fallback.

    The ``reversible`` flag is set to ``False`` when any token appears
    in ``_IRREVERSIBLE_KEYWORDS``, independent of the tier.

    Callers can inject additional context via the ``context`` dict.  If
    ``context["risk_override"]`` is set to ``"low"``, ``"medium"``, or
    ``"high"``, that value takes precedence over keyword matching (useful
    for domain-specific classification logic layered on top).

    Args:
        action: Free-form description of the action to classify.
        context: Optional metadata dict.  Recognised keys:

            ``"risk_override"``
                Bypass keyword matching and force a specific tier.
            ``"target"`` / ``"targets"`` / ``"affected"``
                Entities affected by the action (used in
                ``RiskAssessment.affected``).

    Returns:
        ``RiskAssessment`` with tier, reason, affected entities, and
        reversibility flag.
    """
    import re as _re

    tokens = _re.findall(r"[a-z0-9]+", action.lower())
    _affected_raw: list[str] = []
    if context:
        for _k in ("target", "targets", "affected", "resource", "entity"):
            _val = context.get(_k)
            if _val is None:
                continue
            if isinstance(_val, list):
                _affected_raw.extend(str(v) for v in _val)
            else:
                _affected_raw.append(str(_val))
    if not _affected_raw:
        _affected_raw = _re.findall(r'["\']([^"\']+)["\']', action) + _re.findall(
            r"<([^>]+)>", action
        )
    _seen: set[str] = set()
    affected: list[str] = []
    for _item in _affected_raw:
        if _item not in _seen:
            _seen.add(_item)
            affected.append(_item)

    # Honour explicit caller override first.
    if context:
        override = context.get("risk_override", "").lower()
        if override in ("low", "medium", "high"):
            reversible = not any(t in _IRREVERSIBLE_KEYWORDS for t in tokens)
            return RiskAssessment(
                tier=override,
                reason=f"Risk overridden by caller to '{override}'.",
                affected=affected,
                reversible=reversible,
            )

    reversible = not any(t in _IRREVERSIBLE_KEYWORDS for t in tokens)

    # HIGH — check first to prevent demotion.
    matched_high = [t for t in tokens if t in _HIGH_RISK_KEYWORDS]
    if matched_high:
        return RiskAssessment(
            tier="high",
            reason=(
                f"Action contains high-risk keyword(s): {', '.join(sorted(set(matched_high)))}."
            ),
            affected=affected,
            reversible=reversible,
        )

    # MEDIUM.
    matched_medium = [t for t in tokens if t in _MEDIUM_RISK_KEYWORDS]
    if matched_medium:
        return RiskAssessment(
            tier="medium",
            reason=(
                f"Action contains medium-risk keyword(s): {', '.join(sorted(set(matched_medium)))}."
            ),
            affected=affected,
            reversible=reversible,
        )

    # LOW.
    matched_low = [t for t in tokens if t in _LOW_RISK_KEYWORDS]
    if matched_low:
        return RiskAssessment(
            tier="low",
            reason=(f"Action contains low-risk keyword(s): {', '.join(sorted(set(matched_low)))}."),
            affected=affected,
            reversible=reversible,
        )

    # Default: conservative medium when no keywords match.
    return RiskAssessment(
        tier="medium",
        reason="No recognised risk keywords found; defaulting to medium.",
        affected=affected,
        reversible=reversible,
    )


def gate(
    action: str,
    risk: RiskAssessment | None = None,
    auto_approve_low: bool = True,
) -> ApprovalRequest | None:
    """Decide whether an action requires human approval.

    Args:
        action: The action to evaluate.
        risk: Pre-computed ``RiskAssessment``.  If ``None``, ``assess_risk``
            is called automatically.
        auto_approve_low: When ``True`` (the default), low-risk actions
            are approved automatically and this function returns ``None``.
            Set to ``False`` to surface *all* actions for review regardless
            of tier (useful in high-stakes or audited environments).

    Returns:
        ``None`` if the action is auto-approved.
        ``ApprovalRequest`` if the action requires human review.
    """
    if risk is None:
        risk = assess_risk(action)

    if auto_approve_low and risk.tier == "low":
        return None

    return ApprovalRequest(
        action=action,
        risk=risk,
        preview=preview_action(action, context=None),
    )


def preview_action(
    action: str,
    context: dict[str, Any] | None = None,
) -> str:
    """Generate a human-readable impact preview for a proposed action.

    The preview describes what the action intends to do, which entities
    are affected (if determinable), and a reversibility notice.

    Args:
        action: Free-form description of the proposed action.
        context: Optional metadata; same keys as ``assess_risk``.

    Returns:
        Multi-line plain-text preview string suitable for display in a
        terminal, Slack message, or web form.
    """
    risk = assess_risk(action, context)
    affected = risk.affected

    lines: list[str] = [
        f"Action:       {action}",
        f"Risk tier:    {risk.tier.upper()}",
        f"Reason:       {risk.reason}",
    ]

    if affected:
        entity_str = (
            ", ".join(affected)
            if len(affected) <= 5
            else (", ".join(affected[:5]) + f" ... (+{len(affected) - 5} more)")
        )
        lines.append(f"Affects:      {entity_str}")
    else:
        lines.append("Affects:      (entities not specified)")

    reversibility = (
        "Yes — can be undone." if risk.reversible else ("No — this action cannot be reversed.")
    )
    lines.append(f"Reversible:   {reversibility}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Convenience class wrapper
# ---------------------------------------------------------------------------


class HumanLoopGate:
    """OOP wrapper around ``assess_risk`` and ``gate`` for approval workflows.

    Usage::

        hlg = HumanLoopGate()
        risk = hlg.assess("delete all records")
        result = hlg.check("delete all records", approver=my_approver)
    """

    def assess(self, action: str, context: dict | None = None) -> RiskAssessment:
        """Classify risk level of an action."""
        return assess_risk(action, context)

    def check(
        self,
        action: str,
        context: dict | None = None,
        approver: Callable | None = None,
    ) -> ApprovalResult:
        """Full gate check: assess risk, request approval if needed."""
        request = gate(action)
        if request is None:
            return ApprovalResult(approved=True, feedback="auto_approved_low_risk")
        if approver is not None:
            return approver(request)
        return ApprovalResult(approved=False, feedback="requires_human_review")
