"""
Failure Detectors — 4 automated regression alerts.
===================================================
SDK LAYER: Layer 1 (enhancements). Pure Python.

SPEC Section 5: detects when the brain is:
  1. Being ignored (corrections drop but edit distance doesn't)
  2. Playing safe (acceptance rises but quality flat)
  3. Overfitting (rules increase but misfires increase)
  4. Regressing to mean (output becomes bland, TTR > 0.70)
"""

from __future__ import annotations

from dataclasses import dataclass

from gradata.enhancements.metrics import MetricsWindow

# Blandness threshold from SPEC Section 5 + McCarthy & Jarvis 2010
BLANDNESS_THRESHOLD = 0.70


@dataclass
class Alert:
    """A detected quality regression alert."""
    detector: str = ""
    severity: str = "warning"
    message: str = ""


def detect_being_ignored(
    current: MetricsWindow,
    previous: MetricsWindow | None = None,
) -> list[Alert]:
    """Corrections drop but edit distance doesn't decrease.

    Indicates the brain's rules are being surfaced but the LLM isn't following them.
    Requires baseline (previous window) to detect trend.
    """
    if previous is None:
        return []

    # Corrections dropped but edit distance stayed same or increased
    if (
        current.correction_density < previous.correction_density * 0.5
        and current.edit_distance_avg >= previous.edit_distance_avg * 0.9
    ):
        return [Alert(
            detector="being_ignored",
            severity="warning",
            message=(
                f"Corrections dropped {current.correction_density:.2f} → "
                f"{previous.correction_density:.2f} but edit distance unchanged "
                f"({current.edit_distance_avg:.2f}). Brain may be ignored."
            ),
        )]
    return []


def detect_playing_safe(
    current: MetricsWindow,
    previous: MetricsWindow | None = None,
) -> list[Alert]:
    """Acceptance rises but output quality is flat.

    Indicates the AI is producing generic/safe outputs to avoid corrections.
    Requires baseline to detect trend.
    """
    if previous is None:
        return []

    acceptance_improved = (
        current.rule_success_rate > previous.rule_success_rate + 0.1
    )
    quality_flat = (
        abs(current.edit_distance_avg - previous.edit_distance_avg) < 0.02
    )
    if acceptance_improved and quality_flat:
        return [Alert(
            detector="playing_safe",
            severity="warning",
            message=(
                "Acceptance rate improved but output quality is flat. "
                "Brain may be playing safe (avoiding risk)."
            ),
        )]
    return []


def detect_overfitting(
    current: MetricsWindow,
    previous: MetricsWindow | None = None,
) -> list[Alert]:
    """Rules increase but misfires also increase.

    Indicates the brain is generating too many rules that don't generalize.
    Requires baseline to detect trend.
    """
    if previous is None:
        return []

    if (
        current.rule_misfire_rate > previous.rule_misfire_rate + 0.05
        and current.rule_success_rate < previous.rule_success_rate
    ):
        return [Alert(
            detector="overfitting",
            severity="warning",
            message=(
                f"Misfire rate increased ({previous.rule_misfire_rate:.2f} → "
                f"{current.rule_misfire_rate:.2f}) while success rate dropped. "
                "Brain may be overfitting."
            ),
        )]
    return []


def detect_regression_to_mean(
    current: MetricsWindow,
    previous: MetricsWindow | None = None,
) -> list[Alert]:
    """Output vocabulary diversity drops below threshold.

    Can fire WITHOUT baseline — blandness is absolute, not relative.
    SPEC Section 5: blandness > 0.70 inverted TTR.
    """
    if current.blandness_score > BLANDNESS_THRESHOLD:
        return [Alert(
            detector="regression_to_mean",
            severity="warning",
            message=(
                f"Output blandness score {current.blandness_score:.2f} exceeds "
                f"threshold {BLANDNESS_THRESHOLD}. Brain may be regressing to "
                "generic/safe outputs."
            ),
        )]
    return []


def detect_failures(
    current: MetricsWindow,
    previous: MetricsWindow | None = None,
) -> list[Alert]:
    """Run all 4 failure detectors and return combined alerts."""
    alerts: list[Alert] = []
    alerts.extend(detect_being_ignored(current, previous))
    alerts.extend(detect_playing_safe(current, previous))
    alerts.extend(detect_overfitting(current, previous))
    alerts.extend(detect_regression_to_mean(current, previous))
    return alerts


def format_alerts(alerts: list[Alert]) -> str:
    """Format alerts as human-readable string."""
    if not alerts:
        return "No alerts."
    lines = []
    for a in alerts:
        lines.append(f"[{a.severity.upper()}] {a.detector}: {a.message}")
    return "\n".join(lines)
