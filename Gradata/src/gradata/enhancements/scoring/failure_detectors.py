"""
Automated failure detectors for Gradata.
=================================================
Watches MetricsWindow snapshots for regression patterns and surfaces
alerts before a brain quietly degrades.

Each detector compares the current window against a previous baseline.
All detectors require a previous snapshot — returns an empty list when
``previous`` is None so the caller doesn't have to guard against it.

Public API
----------
detect_failures(current, previous) -> list[Alert]
format_alerts(alerts)              -> str

Individual detectors (also importable):
    detect_being_ignored(current, previous)     -> list[Alert]
    detect_playing_safe(current, previous)      -> list[Alert]
    detect_overfitting(current, previous)       -> list[Alert]
    detect_regression_to_mean(current, previous) -> list[Alert]
"""

from dataclasses import dataclass, field
from typing import Any

from gradata.enhancements.metrics import MetricsWindow

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Alert:
    """A single failure signal emitted by a detector.

    Attributes:
        detector: Machine-readable name of the detector that fired.
        severity: Either ``"warning"`` or ``"critical"``.
        message: Human-readable explanation of what was detected.
        evidence: Supporting numeric data so the caller can log or display
            the exact values that crossed a threshold.
    """

    detector: str
    severity: str  # "warning" | "critical"
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Individual detectors
# ---------------------------------------------------------------------------

def detect_being_ignored(
    current: MetricsWindow,
    previous: MetricsWindow | None,
) -> list[Alert]:
    """Detect when the brain's output is being bypassed without correction.

    Signal: corrections drop (rewrite_rate decreases) but
    edit_distance_avg does *not* decrease at the same pace.  This means
    The user stopped correcting outputs but isn't actually using them —
    the brain is being ignored rather than trusted.

    Thresholds (warning):
        rewrite_rate decreased by >= 10 percentage points
        AND edit_distance_avg decreased by < 5% relative to previous.
    """
    if previous is None or previous.sample_size == 0:
        return []

    rr_delta = previous.rewrite_rate - current.rewrite_rate  # positive = fewer rewrites
    if rr_delta < 0.10:
        # Rewrite rate hasn't dropped meaningfully — no signal.
        return []

    # If edit distance also drops proportionally, the brain is improving.
    # If it *doesn't* drop, rewrites are just being skipped — being ignored.
    if previous.edit_distance_avg == 0:
        return []

    ed_pct_change = (
        current.edit_distance_avg - previous.edit_distance_avg
    ) / previous.edit_distance_avg  # negative = lower edit distance

    # Warning fires when corrections drop sharply but edit distance stays flat
    # (ed_pct_change > -0.05 means less than 5% reduction in edit distance).
    if ed_pct_change > -0.05:
        return [
            Alert(
                detector="being_ignored",
                severity="warning",
                message=(
                    "Correction rate dropped but edit distance is unchanged. "
                    "Brain output may be bypassed rather than trusted."
                ),
                evidence={
                    "rewrite_rate_delta": round(rr_delta, 4),
                    "prev_rewrite_rate": previous.rewrite_rate,
                    "curr_rewrite_rate": current.rewrite_rate,
                    "prev_edit_distance_avg": previous.edit_distance_avg,
                    "curr_edit_distance_avg": current.edit_distance_avg,
                    "ed_pct_change": round(ed_pct_change, 4),
                },
            )
        ]

    return []


def detect_playing_safe(
    current: MetricsWindow,
    previous: MetricsWindow | None,
) -> list[Alert]:
    """Detect when the brain increases acceptance by becoming generic.

    Signal: acceptance rate rises AND blandness score also rises.
    The brain is earning approvals by producing safe, generic output
    rather than genuinely improving.

    Thresholds:
        Warning:  acceptance improves by >= 10pp AND blandness up >= 0.05.
        Critical: acceptance improves by >= 10pp AND blandness up >= 0.15.
    """
    if previous is None or previous.sample_size == 0:
        return []

    prev_acceptance = 1.0 - previous.rewrite_rate
    curr_acceptance = 1.0 - current.rewrite_rate
    acceptance_delta = curr_acceptance - prev_acceptance  # positive = more accepted

    blandness_delta = current.blandness_score - previous.blandness_score  # positive = blander

    if acceptance_delta < 0.10 or blandness_delta < 0.05:
        return []

    severity = "critical" if blandness_delta >= 0.15 else "warning"

    return [
        Alert(
            detector="playing_safe",
            severity=severity,
            message=(
                "Acceptance rate rose alongside blandness score. "
                "Brain may be optimising for approval by producing generic output."
            ),
            evidence={
                "acceptance_delta": round(acceptance_delta, 4),
                "prev_acceptance": round(prev_acceptance, 4),
                "curr_acceptance": round(curr_acceptance, 4),
                "blandness_delta": round(blandness_delta, 4),
                "prev_blandness": previous.blandness_score,
                "curr_blandness": current.blandness_score,
            },
        )
    ]


def detect_overfitting(
    current: MetricsWindow,
    previous: MetricsWindow | None,
) -> list[Alert]:
    """Detect when adding more rules makes misfires worse.

    Signal: rule_misfire_rate increases while the acceptance distribution
    shifts toward more rules being applied (approximated by a higher total
    rule application implied by sample growth).  A simpler proxy: misfire
    rate increases by >= 10 percentage points window-over-window.

    Thresholds:
        Warning:  misfire_rate increased by >= 10pp.
        Critical: misfire_rate increased by >= 20pp.
    """
    if previous is None or previous.sample_size == 0:
        return []

    misfire_delta = current.rule_misfire_rate - previous.rule_misfire_rate  # positive = worse

    if misfire_delta < 0.10:
        return []

    severity = "critical" if misfire_delta >= 0.20 else "warning"

    return [
        Alert(
            detector="overfitting",
            severity=severity,
            message=(
                "Rule misfire rate increased. "
                "New rules may be overfitting to specific sessions."
            ),
            evidence={
                "misfire_delta": round(misfire_delta, 4),
                "prev_misfire_rate": previous.rule_misfire_rate,
                "curr_misfire_rate": current.rule_misfire_rate,
                "prev_rule_success_rate": previous.rule_success_rate,
                "curr_rule_success_rate": current.rule_success_rate,
            },
        )
    ]


def detect_regression_to_mean(
    current: MetricsWindow,
    previous: MetricsWindow | None,
    blandness_warn: float = 0.70,
    blandness_critical: float = 0.85,
) -> list[Alert]:
    """Detect when output vocabulary has drifted into generic territory.

    Signal: blandness_score exceeds threshold, indicating the brain's
    recent outputs lack vocabulary diversity.

    Thresholds are configurable per domain — sales emails are inherently
    more repetitive than research reports, so higher thresholds are appropriate.

    Args:
        current: Current metrics window.
        previous: Previous metrics window (optional, for severity context).
        blandness_warn: Warning threshold (default 0.70). Sales brains may use 0.80.
        blandness_critical: Critical threshold (default 0.85). Sales brains may use 0.92.
    """
    alerts: list[Alert] = []

    if current.blandness_score >= blandness_warn:
        severity = "critical" if current.blandness_score >= blandness_critical else "warning"
        evidence: dict[str, Any] = {
            "curr_blandness": current.blandness_score,
            "threshold": 0.70,
        }
        if previous is not None:
            evidence["prev_blandness"] = previous.blandness_score
            evidence["blandness_delta"] = round(
                current.blandness_score - previous.blandness_score, 4
            )

        alerts.append(
            Alert(
                detector="regression_to_mean",
                severity=severity,
                message=(
                    f"Blandness score {current.blandness_score:.3f} exceeds "
                    "threshold 0.70. Brain output is becoming generic."
                ),
                evidence=evidence,
            )
        )

    return alerts


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------

def detect_failures(
    current: MetricsWindow,
    previous: MetricsWindow | None = None,
) -> list[Alert]:
    """Run all failure detectors and return combined alerts.

    Detectors that require a baseline (``previous``) return nothing when
    it is absent.  Only :func:`detect_regression_to_mean` can fire without
    a baseline.

    Args:
        current: MetricsWindow from the most recent window.
        previous: MetricsWindow from the prior window (or None on first run).

    Returns:
        List of :class:`Alert` objects, possibly empty.
    """
    alerts: list[Alert] = []
    alerts.extend(detect_being_ignored(current, previous))
    alerts.extend(detect_playing_safe(current, previous))
    alerts.extend(detect_overfitting(current, previous))
    alerts.extend(detect_regression_to_mean(current, previous))
    return alerts


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------

def format_alerts(alerts: list[Alert]) -> str:
    """Format a list of alerts as a human-readable string.

    Args:
        alerts: List returned by :func:`detect_failures`.

    Returns:
        Multi-line string.  Returns ``"No alerts."`` when the list is empty.
    """
    if not alerts:
        return "No alerts."

    lines: list[str] = [f"Failure Alerts ({len(alerts)} detected):"]
    for a in alerts:
        icon = "[CRITICAL]" if a.severity == "critical" else "[WARNING]"
        lines.append(f"  {icon} {a.detector}: {a.message}")
        for k, v in a.evidence.items():
            lines.append(f"      {k}: {v}")
    return "\n".join(lines)
