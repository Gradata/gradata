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


# ---------------------------------------------------------------------------
# Core Functions
# ---------------------------------------------------------------------------


def _extract_tag(tags: list[str], prefix: str) -> str | None:
    """Extract first tag value matching prefix (e.g., 'entity:' → 'Hassan Ali')."""
    for tag in tags:
        if tag.startswith(prefix):
            return tag[len(prefix):]
    return None


def collect_outcomes(session: int, ctx=None) -> list[dict]:
    """Query DELTA_TAG events with outcome tags from a session.

    Returns list of dicts with: outcome, entity, channel, event_id, tags.
    Skips events without an outcome tag.
    """
    try:
        from gradata._events import query
        events = query(event_type="DELTA_TAG", session=session, ctx=ctx)
    except ImportError:
        return []

    results = []
    for evt in events:
        tags = evt.get("tags", [])
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except (json.JSONDecodeError, TypeError):
                tags = []

        outcome = _extract_tag(tags, "outcome:")
        if not outcome:
            # Check data dict too
            data = evt.get("data", {})
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except (json.JSONDecodeError, TypeError):
                    data = {}
            outcome = data.get("outcome")

        if not outcome:
            continue

        results.append({
            "outcome": outcome,
            "entity": _extract_tag(tags, "entity:"),
            "channel": _extract_tag(tags, "channel:"),
            "event_id": evt.get("id"),
            "tags": tags,
        })
    return results


def attribute_to_rules(
    outcomes: list[dict],
    session: int,
    ctx=None,
) -> list[OutcomeAttribution]:
    """Match outcomes to rules that were active when outputs were generated.

    Uses OUTPUT events' `rules_applied` field for direct attribution.
    Falls back to entity-matching if rules_applied is empty.
    """
    if not outcomes:
        return []

    try:
        from gradata._events import query
        output_events = query(event_type="OUTPUT", session=session, ctx=ctx)
    except ImportError:
        return []

    attributions: list[OutcomeAttribution] = []

    for outcome_dict in outcomes:
        outcome = outcome_dict["outcome"]
        entity = outcome_dict.get("entity", "")

        # Determine signal type
        if outcome in POSITIVE_OUTCOMES:
            signal_type = "acceptance"
            weight = EXTERNAL_ACCEPTANCE_WEIGHT
        elif outcome in NEGATIVE_OUTCOMES:
            signal_type = "contradiction"
            weight = EXTERNAL_CONTRADICTION_WEIGHT
        else:
            continue  # neutral — no signal

        # Find matching output events (by entity tag or session proximity)
        for output_evt in output_events:
            data = output_evt.get("data", {})
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except (json.JSONDecodeError, TypeError):
                    data = {}

            rules_applied = data.get("rules_applied", [])
            output_type = data.get("output_type", "general")

            # Entity matching: check if this output was for the same entity
            output_tags = output_evt.get("tags", [])
            if isinstance(output_tags, str):
                try:
                    output_tags = json.loads(output_tags)
                except (json.JSONDecodeError, TypeError):
                    output_tags = []
            output_entity = _extract_tag(output_tags, "entity:")

            # Match by entity if available, otherwise attribute to all outputs in session
            if entity and output_entity and entity.lower() != output_entity.lower():
                continue

            # For negative outcomes, only attribute if output type maps to a category
            if signal_type == "contradiction" and output_type not in OUTPUT_CATEGORY_MAP:
                continue

            category = OUTPUT_CATEGORY_MAP.get(output_type, "GENERAL")

            # Attribute to each rule that was active for this output
            for rule_id in rules_applied:
                attributions.append(OutcomeAttribution(
                    rule_id=rule_id,
                    outcome=outcome,
                    signal_type=signal_type,
                    weight=weight,
                    category=category,
                    output_type=output_type,
                ))

    return attributions


def compute_external_confidence_delta(
    attributions: list[OutcomeAttribution],
) -> dict[str, float]:
    """Compute per-rule confidence deltas from outcome attributions.

    Caps at MAX_SIGNALS_PER_RULE_PER_SESSION per rule.
    Returns {rule_id: delta} where delta can be positive or negative.
    """
    from gradata.enhancements.self_improvement import ACCEPTANCE_BONUS, CONTRADICTION_PENALTY

    rule_signals: dict[str, list[OutcomeAttribution]] = {}
    for attr in attributions:
        rule_signals.setdefault(attr.rule_id, []).append(attr)

    deltas: dict[str, float] = {}
    for rule_id, signals in rule_signals.items():
        # Cap signals per rule per session
        capped = signals[:MAX_SIGNALS_PER_RULE_PER_SESSION]

        delta = 0.0
        for signal in capped:
            if signal.signal_type == "acceptance":
                delta += ACCEPTANCE_BONUS * signal.weight
            elif signal.signal_type == "contradiction":
                delta += CONTRADICTION_PENALTY * signal.weight

        deltas[rule_id] = round(delta, 4)

    return deltas


def process_session_outcomes(
    session: int | None = None,
    ctx=None,
) -> dict[str, float]:
    """Main entry point: process external outcomes for a session.

    Returns {rule_id: confidence_delta} dict.
    Idempotent: emits OUTCOME_FEEDBACK_PROCESSED event on completion.
    Returns empty dict if already processed or insufficient data.
    """
    # Resolve session
    if session is None:
        try:
            from gradata._events import get_current_session
            session = get_current_session()
        except Exception:
            return {}

    # Idempotency check
    try:
        from gradata._events import emit, query
        existing = query(
            event_type="OUTCOME_FEEDBACK_PROCESSED",
            session=session,
            ctx=ctx,
        )
        if existing:
            return {}
    except ImportError:
        return {}

    # Cold start check: need MIN_OUTCOMES_TO_ACTIVATE total outcomes in history
    try:
        all_outcomes = query(event_type="DELTA_TAG", ctx=ctx, limit=MIN_OUTCOMES_TO_ACTIVATE + 1)
        outcome_count = sum(
            1 for evt in all_outcomes
            if any(
                t.startswith("outcome:") for t in (
                    evt.get("tags", []) if isinstance(evt.get("tags"), list)
                    else json.loads(evt.get("tags", "[]"))
                )
            )
        )
        if outcome_count < MIN_OUTCOMES_TO_ACTIVATE:
            _log.debug(
                "Outcome feedback skipped: %d outcomes < %d minimum",
                outcome_count, MIN_OUTCOMES_TO_ACTIVATE,
            )
            return {}
    except Exception:
        return {}

    # Process
    outcomes = collect_outcomes(session, ctx=ctx)
    if not outcomes:
        return {}

    attributions = attribute_to_rules(outcomes, session, ctx=ctx)
    if not attributions:
        return {}

    deltas = compute_external_confidence_delta(attributions)

    # Mark as processed (idempotency)
    try:
        emit(
            "OUTCOME_FEEDBACK_PROCESSED",
            "outcome_feedback:process",
            {
                "session": session,
                "outcomes_processed": len(outcomes),
                "attributions": len(attributions),
                "rules_affected": len(deltas),
            },
            tags=["system:outcome_feedback"],
            session=session,
            ctx=ctx,
        )
    except Exception as e:
        _log.warning("Failed to emit OUTCOME_FEEDBACK_PROCESSED: %s", e)

    return deltas
