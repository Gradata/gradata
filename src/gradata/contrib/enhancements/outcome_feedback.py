"""
Outcome Feedback — External signal → confidence feedback loop.
==============================================================
SDK LAYER: Layer 1 (enhancements). Pure Python.

Closes the loop between brain-generated outputs and real-world outcomes.
When an email gets a reply, a deal advances, or a meeting is booked,
the rules that influenced that output get credit (or penalty).

External signals are weaker than user corrections:
  - User correction: 1.0x (ground truth, human edited real text)
  - External positive: 0.5x (attribution uncertain)
  - External negative: 0.3x (confounding variables)
  - No reply/neutral: 0.0x (ambiguous, no signal)

Safeguards:
  - Min 20 outcomes before activation (cold start protection)
  - Max 3 signals per rule per session (volume gaming cap)
  - Can't cross tier boundaries (external signals alone can't promote)
  - Idempotent (OUTCOME_FEEDBACK_PROCESSED event prevents double-counting)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXTERNAL_ACCEPTANCE_WEIGHT = 0.5
EXTERNAL_CONTRADICTION_WEIGHT = 0.3
MAX_SIGNALS_PER_RULE_PER_SESSION = 3
MIN_OUTCOMES_TO_ACTIVATE = 20

POSITIVE_OUTCOMES = frozenset({
    "positive-reply", "meeting-booked", "deal-advanced", "demo-completed",
})
NEGATIVE_OUTCOMES = frozenset({
    "deal-lost", "negative-reply",
})
# no-reply, ghosted, pending, objection-raised, reply = neutral (no signal)

# Map output_type → lesson category for negative attribution
OUTPUT_CATEGORY_MAP: dict[str, str] = {
    "email": "DRAFTING",
    "email_draft": "DRAFTING",
    "demo_prep": "DEMO_PREP",
    "call_script": "POSITIONING",
    "research": "ACCURACY",
    "cold_call_script": "POSITIONING",
    "cheat_sheet": "DEMO_PREP",
}

# Tier ceilings — external signals can't push confidence past these
TIER_CEILINGS: dict[str, float] = {
    "INSTINCT": 0.59,
    "PATTERN": 0.89,
    "RULE": 1.00,
}


@dataclass
class OutcomeAttribution:
    """Links a real-world outcome to a brain rule."""
    rule_id: str
    outcome: str
    signal_type: str    # "acceptance" | "contradiction" | "neutral"
    weight: float       # 0.0-1.0
    category: str       # lesson category for the rule
    output_type: str    # what kind of output produced the outcome


