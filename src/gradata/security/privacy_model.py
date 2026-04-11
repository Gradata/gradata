"""Privacy model — differential privacy + sanitization for cloud sharing.

Implements three privacy primitives for the Gradata sharing pipeline:

1. **Laplace noise** — calibrated DP noise on usage statistics so that
   individual fire/misfire counts cannot reveal exact user behavior.
2. **Sanitization** — strips PII-risk fields (drafts, corrections, event IDs)
   before any lesson leaves the local brain.
3. **k-anonymity gate** — a rule must exist in k+ brains before it can
   appear in the marketplace, preventing unique-rule re-identification.

Text-level re-identification (inferring a user from rule description text)
is explicitly out of scope for v1.  See THREAT_MODEL.md for details.
"""

from __future__ import annotations

import math
import random
from typing import Any

MIN_K_ANONYMITY = 5  # Rule must exist in 5+ brains before marketplace listing


def add_laplace_noise(
    value: float,
    sensitivity: float = 1.0,
    epsilon: float = 1.0,
) -> float:
    """Add calibrated Laplace noise for differential privacy.

    Higher epsilon = less noise (less privacy, more utility).
    Lower epsilon = more noise (more privacy, less utility).

    The Laplace mechanism satisfies epsilon-differential privacy when
    ``scale = sensitivity / epsilon``.

    Args:
        value: The true numeric value.
        sensitivity: Maximum change in value from one individual's data.
        epsilon: Privacy budget parameter (> 0).

    Returns:
        The value with added Laplace noise.
    """
    scale = sensitivity / epsilon
    # Inverse CDF sampling of Laplace(0, scale)
    u = random.random() - 0.5
    laplace = -scale * math.copysign(1, u) * math.log(1 - 2 * abs(u))
    return value + laplace


def sanitize_for_sharing(
    lesson_dict: dict[str, Any],
    epsilon: float = 1.0,
) -> dict[str, Any]:
    """Prepare a lesson for cloud sharing with privacy protections.

    Pipeline:
        1. Add Laplace noise to: fire_count, misfire_count, sessions_since_fire
        2. Strip PII-risk fields: example_draft, example_corrected,
           correction_event_ids, memory_ids, agent_type
        3. Keep: description, category, confidence, state, path
           (needed for tree structure and matching)

    NOTE: Text-level re-identification (inferring user from rule descriptions)
    is explicitly OUT OF SCOPE for v1.  The description field is shared as-is.
    Future work: LLM-based text redaction before export.

    Args:
        lesson_dict: Raw lesson dictionary from the local brain.
        epsilon: Privacy budget for Laplace noise on statistics.

    Returns:
        A new dictionary safe for cloud transmission.
    """
    sanitized = dict(lesson_dict)

    # Add noise to statistics
    for field in ("fire_count", "misfire_count", "sessions_since_fire"):
        if field in sanitized and isinstance(sanitized[field], (int, float)):
            sanitized[field] = max(
                0,
                round(add_laplace_noise(float(sanitized[field]), epsilon=epsilon)),
            )

    # Strip PII-risk fields
    for field in (
        "example_draft",
        "example_corrected",
        "correction_event_ids",
        "memory_ids",
        "agent_type",
    ):
        sanitized.pop(field, None)

    return sanitized


def check_k_anonymity(rule_count_across_brains: int) -> bool:
    """Check if a rule meets the k-anonymity threshold for marketplace listing.

    A rule that exists in fewer than MIN_K_ANONYMITY brains could be used
    to re-identify the user who created it.  This gate prevents listing
    until sufficient adoption dilutes that signal.

    Args:
        rule_count_across_brains: Number of distinct brains containing this rule.

    Returns:
        True if the rule is safe to list in the marketplace.
    """
    return rule_count_across_brains >= MIN_K_ANONYMITY
