"""Experiment knobs for Beta-LB graduation gating.

These settings belong to GRA-210 and intentionally keep runtime behavior
backwards-compatible by default. Production default remains 0.75, while
`GRADATA_BETA_LB_THRESHOLD` can be set to `0.55` for the staged experiment.
"""

from __future__ import annotations

import math
import os

# GRA-210: graduation_threshold experiment parameter for Beta-LB lower-bound checks.
GRA_210_EXPERIMENT = "GRA-210"
GRA_210_GRADUATION_THRESHOLD_ENV = "GRADATA_BETA_LB_THRESHOLD"
GRA_210_GRADUATION_THRESHOLD_DEFAULT = 0.75


def read_beta_lb_threshold(default: float = GRA_210_GRADUATION_THRESHOLD_DEFAULT) -> float:
    """Read the Beta-LB threshold override from env.

    Returns a float clipped to [0.0, 1.0], or ``default`` when parsing fails.
    """

    raw_value = os.environ.get(GRA_210_GRADUATION_THRESHOLD_ENV)
    if raw_value is None:
        return default

    try:
        threshold = float(raw_value)
    except (TypeError, ValueError):
        return default

    if not math.isfinite(threshold):
        return default

    return min(max(threshold, 0.0), 1.0)
