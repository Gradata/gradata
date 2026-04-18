"""
Graduation submodule for the self_improvement package.

Contains: _passes_beta_lb_gate() and graduate().

All constants are imported from _confidence to avoid duplication.
"""

from __future__ import annotations

import logging

from ..._types import (
    Lesson,
    LessonState,
    RuleMetadata,
    transition,
)
from ._confidence import (
    _GRADUATION_DEDUP_THRESHOLD,
    KILL_LIMITS,
    MACHINE_KILL_LIMITS,
    MIN_APPLICATIONS_FOR_PATTERN,
    MIN_APPLICATIONS_FOR_RULE,
    PATTERN_THRESHOLD,
    RULE_THRESHOLD,
    _classify_correction_direction,
    is_hook_enforced,
)

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Graduation
# ---------------------------------------------------------------------------


def _passes_beta_lb_gate(lesson: Lesson) -> bool:
    """Beta lower-bound gate on PATTERN -> RULE promotion.

    Opt-in via env var ``GRADATA_BETA_LB_GATE`` (default off). When enabled,
    requires the 5th-percentile lower bound of Beta(α, β) to meet the
    configured threshold (``GRADATA_BETA_LB_THRESHOLD``, default 0.85) AND
    at least ``GRADATA_BETA_LB_MIN_FIRES`` observations (default 5).

    Rationale: the v4 ablation min2022 random-label control showed that
    ~15–20% of current RULE-tier graduations are calibrated by format,
    not content. The Beta posterior captures uncertainty the mean
    (lesson.confidence) discards. Feature-flagged so production
    calibration is unchanged until this is measured in-band.
    """
    import os

    if os.environ.get("GRADATA_BETA_LB_GATE", "").lower() not in ("1", "true", "yes", "on"):
        return True  # gate disabled — defer to existing conf + fire_count checks

    import math

    try:
        threshold = float(os.environ.get("GRADATA_BETA_LB_THRESHOLD", "0.85"))
        if not math.isfinite(threshold):
            threshold = 0.85
        threshold = min(max(threshold, 0.0), 1.0)
    except (TypeError, ValueError):
        threshold = 0.85
    try:
        min_fires = max(0, int(os.environ.get("GRADATA_BETA_LB_MIN_FIRES", "5")))
    except (TypeError, ValueError):
        min_fires = 5

    if lesson.fire_count < min_fires:
        return False

    alpha = getattr(lesson, "alpha", 1.0)
    beta_param = getattr(lesson, "beta_param", 1.0)
    from ...rules.rule_engine import _beta_ppf_05

    return _beta_ppf_05(alpha, beta_param) >= threshold


def graduate(
    lessons: list[Lesson],
    *,
    maturity: str = "INFANT",
    renter: bool = False,
    machine_mode: bool = False,
    salt: str = "",
    brain=None,
) -> tuple[list[Lesson], list[Lesson]]:
    """Apply state transitions and split into active vs graduated.

    Mutates lessons in-place. Returns (active, graduated) where:
      - active = INSTINCT + PATTERN (still adapting)
      - graduated = RULE + UNTESTABLE + KILLED + ARCHIVED (terminal or proven)

    SPEC guardrail: no promotion from silence. fire_count must meet
    minimum thresholds even if confidence is high enough:
      - INSTINCT -> PATTERN requires fire_count >= 3 (MIN_APPLICATIONS_FOR_PATTERN).
      - PATTERN -> RULE requires fire_count >= 5 (MIN_APPLICATIONS_FOR_RULE).
    A single session cannot fast-track promotion; the fire-count gates are
    non-bypassable regardless of confidence level.

    Args:
        lessons: Lessons to evaluate for promotion/demotion/kill.
        maturity: Brain maturity phase for kill-switch thresholds.
        renter: If True, skip all mutations (renter mode: lessons frozen).
        machine_mode: If True, use extended kill limits for machine contexts.
        salt: Per-brain salt for non-deterministic threshold jitter (+/-5%).
    """
    # Compute effective thresholds (salted or default)
    if salt:
        from ...security.brain_salt import salt_threshold

        eff_pattern_threshold = salt_threshold(PATTERN_THRESHOLD, salt, "PATTERN")
        eff_rule_threshold = salt_threshold(RULE_THRESHOLD, salt, "RULE")
    else:
        eff_pattern_threshold = PATTERN_THRESHOLD
        eff_rule_threshold = RULE_THRESHOLD
    if renter:
        active = [l for l in lessons if l.state in (LessonState.INSTINCT, LessonState.PATTERN)]
        graduated = [
            l for l in lessons if l.state not in (LessonState.INSTINCT, LessonState.PATTERN)
        ]
        return active, graduated

    eff_kill_limits = MACHINE_KILL_LIMITS if machine_mode else KILL_LIMITS
    kill_limit = eff_kill_limits.get(maturity, eff_kill_limits["INFANT"])

    # Pre-compute rule state for adversarial gates (avoids N+1 inside loop)
    existing_rules = [l for l in lessons if l.state == LessonState.RULE]
    existing_rule_descs = [r.description for r in existing_rules]
    existing_rule_summary = " | ".join(d for d in existing_rule_descs[:10])

    for lesson in lessons:
        if lesson.state in (LessonState.KILLED, LessonState.ARCHIVED):
            continue

        # Safety assertion: warn if a single session caused an unusually
        # large confidence jump (possible runaway boosting).
        pre_conf = getattr(lesson, "_pre_session_confidence", None)
        if isinstance(pre_conf, (int, float)):
            jump = lesson.confidence - pre_conf
            if jump > eff_pattern_threshold:
                _log.warning(
                    "Safety assertion: confidence jump %.2f exceeds PATTERN_THRESHOLD %.2f for %s: %s",
                    jump,
                    eff_pattern_threshold,
                    lesson.category,
                    lesson.description[:60],
                )

        if lesson.pending_approval:
            continue  # Awaiting human review — skip graduation entirely

        # ONE_OFF scoped lessons never graduate past INSTINCT
        block_promotion = False
        if lesson.scope_json:
            try:
                import json as _json

                _scope = _json.loads(lesson.scope_json)
                if _scope.get("correction_scope") == "one_off" and lesson.state in (
                    LessonState.INSTINCT,
                    LessonState.PATTERN,
                ):
                    block_promotion = True
            except (ValueError, TypeError):
                pass

        # Per-session invariant: at most ONE graduation tier transition per
        # session. If update_confidence already moved this lesson between
        # tiers (INSTINCT->PATTERN or PATTERN->INSTINCT), do not stack
        # another transition in graduate(). See MAX_PER_SESSION_DELTA
        # comment and gap-analysis/01-internal-audit.md Gap 4.
        pre_state_graduate = getattr(lesson, "_pre_session_state", None)
        if pre_state_graduate is not None and pre_state_graduate != lesson.state:
            block_promotion = True

        # UNTESTABLE lessons: check if they should be killed (enough idle sessions)
        if lesson.state == LessonState.UNTESTABLE:
            if lesson.sessions_since_fire >= kill_limit + 5:
                try:
                    lesson.state = transition(lesson.state, "kill")
                    lesson.kill_reason = f"untestable_expired: {lesson.sessions_since_fire} idle sessions (limit: {kill_limit + 5})"
                except ValueError:
                    pass
            continue

        # Kill: confidence at zero
        if lesson.confidence <= 0.0:
            try:
                lesson.state = transition(lesson.state, "kill")
                lesson.kill_reason = "zero_confidence: accumulated penalties drove confidence to 0"
            except ValueError:
                pass
            continue

        # Kill: untestable (too many sessions without a fire)
        if lesson.sessions_since_fire >= kill_limit:
            if lesson.state == LessonState.UNTESTABLE:
                try:
                    lesson.state = transition(lesson.state, "kill")
                    lesson.kill_reason = f"untestable_idle: {lesson.sessions_since_fire} sessions without firing (limit: {kill_limit})"
                except ValueError:
                    pass
                continue
            if lesson.state in (LessonState.INSTINCT, LessonState.PATTERN):
                lesson.state = LessonState.UNTESTABLE
                lesson.kill_reason = f"moved_to_untestable: {lesson.sessions_since_fire} sessions without firing (limit: {kill_limit})"
                continue

        # Promote PATTERN -> RULE (with adversarial gates + wording refinement)
        if (
            not block_promotion
            and lesson.state == LessonState.PATTERN
            and lesson.confidence >= eff_rule_threshold
            and lesson.fire_count >= MIN_APPLICATIONS_FOR_RULE
            and _passes_beta_lb_gate(lesson)
        ):
            blocked = False

            # Gate 1: dedup — skip if too similar to an existing rule.
            # TODO: At 5,000+ rules, pre-compute TF-IDF vectors for existing_rules
            # outside the lesson loop to avoid redundant tokenization (O(n*m) → O(n+m)).
            try:
                from ..similarity import semantic_similarity

                for existing in existing_rules:
                    sim = semantic_similarity(lesson.description, existing.description)
                    if sim > _GRADUATION_DEDUP_THRESHOLD:
                        blocked = True
                        _log.debug(
                            "Graduation blocked (duplicate): %.2f sim with '%s'",
                            sim,
                            existing.description[:60],
                        )
                        break
            except ImportError:
                pass

            # Gate 2: adversarial — skip if contradicts an existing rule
            if not blocked:
                try:
                    direction = _classify_correction_direction(
                        lesson.description,
                        existing_rule_summary,
                    )
                    if direction == "CONTRADICTING":
                        blocked = True
                        _log.debug(
                            "Graduation blocked (contradiction): '%s'", lesson.description[:60]
                        )
                except Exception:
                    pass

            # Gate 3: paraphrase robustness — rule must match its own rewording.
            # If word-reordered text scores <25% similar, the rule's meaning depends
            # too heavily on word order and won't generalize to rephrased corrections.
            if not blocked:
                try:
                    from ..similarity import semantic_similarity

                    words = lesson.description.split()
                    if len(words) >= 4:
                        mid = len(words) // 2
                        paraphrase = " ".join(words[mid:] + words[:mid])
                        sim = semantic_similarity(lesson.description, paraphrase)
                        if sim < 0.25:
                            blocked = True
                            _log.debug(
                                "Graduation blocked (fragile wording): sim=%.2f '%s'",
                                sim,
                                lesson.description[:60],
                            )
                except ImportError:
                    pass

            if blocked:
                continue

            # Refine rule wording before graduation
            try:
                from ...contrib.patterns.tree_of_thoughts import evaluate_rule_candidates

                result = evaluate_rule_candidates(lesson.description, existing_rule_descs)
                if result.best.content and result.best.score > 0.3:
                    lesson.description = result.best.content
            except Exception:
                pass  # ToT is optional; graduate with original wording
            lesson.state = transition(lesson.state, "promote")

            # Rule-to-hook graduation: attempt to install a deterministic
            # PreToolUse hook for this newly-minted RULE. On success, mark
            # ``lesson.metadata.how_enforced = "hooked"`` so the Python-side
            # rule_enforcement soft-reminder dedups it (the hook now enforces).
            # Never raises out of graduate() — any failure falls back to
            # soft prompt injection silently.
            try:
                from .. import rule_to_hook

                desc = lesson.description or ""
                if desc and not is_hook_enforced(lesson):
                    candidate = rule_to_hook.classify_rule(
                        desc, confidence=float(lesson.confidence)
                    )
                    # Council empirical gate: fire_count + distinct sessions
                    # + zero human reversals (last 30d). If any fails, skip
                    # hook generation — rule stays as text injection.
                    passed, gate_reason = rule_to_hook._passes_empirical_gate(lesson)
                    if not passed:
                        _log.debug(
                            "rule-to-hook promotion blocked by empirical gate: %s",
                            gate_reason,
                        )
                    else:
                        gen_result = rule_to_hook.try_generate(
                            candidate,
                            brain=brain,
                            source="graduate",
                        )
                        if gen_result.installed:
                            if lesson.metadata is None:
                                lesson.metadata = RuleMetadata()
                            lesson.metadata.how_enforced = "hooked"
            except Exception:
                pass  # Hook generation is best-effort; never break graduation.
            continue

        # Promote INSTINCT -> PATTERN
        # H1 fix: strict > prevents a lesson born at INITIAL_CONFIDENCE (0.60)
        # from satisfying PATTERN_THRESHOLD (0.60) without any earned bonus.
        if (
            not block_promotion
            and lesson.state == LessonState.INSTINCT
            and lesson.confidence > eff_pattern_threshold
            and lesson.fire_count >= MIN_APPLICATIONS_FOR_PATTERN
        ):
            lesson.state = transition(lesson.state, "promote")
            continue

        # Demote PATTERN -> INSTINCT
        if lesson.state == LessonState.PATTERN and lesson.confidence < eff_pattern_threshold:
            lesson.state = transition(lesson.state, "demote")
            continue

    # Split into active vs graduated
    active = [l for l in lessons if l.state in (LessonState.INSTINCT, LessonState.PATTERN)]
    graduated = [l for l in lessons if l.state not in (LessonState.INSTINCT, LessonState.PATTERN)]
    return active, graduated
