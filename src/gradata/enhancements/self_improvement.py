"""
Procedural Memory — INSTINCT → PATTERN → RULE graduation pipeline.
===================================================================
SDK LAYER: Layer 1 (enhancements). Imports from Layer 0 (patterns)
and shared types only.

This is the open-source graduation engine. Corrections become procedural
memory: confidence scoring, lesson parsing, FSRS-inspired graduation,
adversarial validation, and formatting.

The proprietary cloud version (gradata_cloud.graduation.self_improvement)
adds FSRS-based scheduling and multi-brain optimization on top.
"""

from __future__ import annotations

import logging
import re

from gradata._types import (
    CorrectionType,
    Lesson,
    LessonState,
    RuleMetadata,
    transition,
)

_log = logging.getLogger(__name__)


def is_hook_enforced(lesson: Lesson) -> bool:
    """True if this lesson is enforced by an installed generated hook.

    Reads structured metadata first (``lesson.metadata.how_enforced == "hooked"``).
    Falls back to the legacy ``[hooked]`` description prefix so existing
    lessons.md files still work until they're rewritten.
    """
    md = getattr(lesson, "metadata", None)
    if md is not None and getattr(md, "how_enforced", "") == "hooked":
        return True
    desc = getattr(lesson, "description", "") or ""
    return desc.lstrip().startswith("[hooked]")

# ---------------------------------------------------------------------------
# Constants (SPEC-aligned, research-backed)
# ---------------------------------------------------------------------------

INITIAL_CONFIDENCE = 0.60
PATTERN_THRESHOLD = 0.60
# RULE_THRESHOLD is 0.90 to match the hard floor enforced at injection time
# by validate_assumptions in rule_engine.py. Keeping graduation below that
# floor silently blocks freshly-promoted rules from ever being injected,
# which the audit (gap-analysis/01-internal-audit.md #1.1) flagged as
# non-deterministic behaviour. The injection gate wins because it is the
# one that actually governs which rules reach the model.
RULE_THRESHOLD = 0.90
MIN_APPLICATIONS_FOR_PATTERN = 3
MIN_APPLICATIONS_FOR_RULE = 3

# Misfire is worse than contradiction (rule was completely irrelevant)
MISFIRE_PENALTY = -0.15
# Calibrated from 2992 real events across 76 sessions (calibrate_constants.py).
# Original: -0.24 (2:1 ratio). Calibrated: -0.10 (1:1 ratio).
# Stress test confirmed: 2:1 caused 74 kills vs 19 promotions (over-punishing).
CONTRADICTION_PENALTY = -0.17

ACCEPTANCE_BONUS = 0.20
# v2.3: survival is flat (no severity scaling)
SURVIVAL_BONUS = 0.08
# Preferences (user taste) decay 50% slower — they're stable signals
PREFERENCE_DECAY_DAMPER = 0.5
# Explicit contradiction acceleration: when direction is CONTRADICTING,
# multiply penalty by this factor for faster preference reversal.
# Applied on top of streak multiplier (see _contradiction_streak_multiplier).
CONTRADICTION_ACCELERATION = 1.5
# Consecutive contradictions accelerate: 1st=1.0x, 2nd=1.5x, 3rd=2.0x, etc.
CONTRADICTION_STREAK_STEP = 0.5
# Severity-aware contradiction boost: rewrite contradictions hit harder
CONTRADICTION_SEVERITY_BOOST: dict[str, float] = {
    "trivial": 0.8,  # trivial contradictions are soft
    "minor": 0.9,
    "moderate": 1.0,  # baseline
    "major": 1.65,  # major contradictions get 65% boost
    "rewrite": 1.8,  # rewrite contradictions get 80% boost
}
# Cooling period: after N contradictions in a row, block survival bonus
# for this many sessions. Prevents oscillation during preference changes.
CONTRADICTION_COOLING_SESSIONS = 2

# SPEC Section 1: maturity-aware kill switches (relevant cycles only)
KILL_LIMITS: dict[str, int] = {
    "INFANT": 8,  # 0-50 sessions — unproven, die fast
    "ADOLESCENT": 12,  # 50-100 sessions — some evidence, moderate grace
    "MATURE": 15,  # 100-200 sessions — proven useful, longer grace
    "STABLE": 20,  # 200+ sessions — battle-tested, longest grace
}

# Severity multipliers for contradiction penalty
# Typo fix barely dents confidence; rewrite hits hard
SEVERITY_WEIGHTS: dict[str, float] = {
    "trivial": 0.20,  # typo fix: -0.10 * 0.20 = -0.02
    "minor": 0.50,  # word swap: -0.10 * 0.50 = -0.05
    "moderate": 0.80,  # sentence rewrite: -0.10 * 0.80 = -0.08
    "major": 1.00,  # significant change: -0.10 * 1.00 = -0.10
    "rewrite": 1.30,  # complete rewrite: -0.10 * 1.30 = -0.13
}

# Legacy survival severity weights (v2.3: survival is flat 0.08, these kept
# for backward compat with tests and cloud version)
SURVIVAL_SEVERITY_WEIGHTS: dict[str, float] = {
    "trivial": 0.30,
    "minor": 0.60,
    "moderate": 0.80,
    "major": 1.00,
    "rewrite": 1.20,
}

# ---------------------------------------------------------------------------
# Machine-context FSRS parameters (stress test, simulation, bulk processing)
# Machine corrections arrive at high volume (60+/session) with 0% approval.
# Base penalty is already calibrated (1:1 ratio), but machine context needs
# even softer treatment since ALL outputs get corrected (no approval signal).
# ---------------------------------------------------------------------------
MACHINE_CONTRADICTION_PENALTY = -0.06
MACHINE_ACCEPTANCE_BONUS = 0.16
MACHINE_KILL_LIMITS: dict[str, int] = {
    "INFANT": 16,
    "ADOLESCENT": 20,
    "MATURE": 24,
    "STABLE": 30,
}
MACHINE_SEVERITY_WEIGHTS: dict[str, float] = {
    "trivial": 0.10,
    "minor": 0.25,
    "moderate": 0.50,
    "major": 0.80,
    "rewrite": 1.00,
}

# Graduation gate thresholds
_GRADUATION_DEDUP_THRESHOLD = 0.85  # Near-duplicate rule detection

# Per-step compound-penalty ceiling.
# gap-analysis/01-internal-audit.md #1.3: without a cap, a single rewrite
# contradiction on a RULE at 0.90 can compound to ~0.63 in one tick
# (base 0.17 * FSRS ~1.22 * severity 1.30 * ACCELERATION 1.50 *
# streak 1.00 * sev_boost 1.80 * rule_override 1.20). Combined with the
# Bayesian blend that follows, the update oscillates under alternating
# corrections. 0.20 is one graduation tier's worth of confidence
# (INSTINCT->PATTERN band) — the maximum a single correction should
# ever move the rule in one step. Matches MAX_PER_SESSION_DELTA so that
# one correction cannot chain two tier demotions in a single session.
MAX_PER_STEP_PENALTY = 0.20

# Per-session net confidence-delta ceiling. Caps the Sybil attack where
# a burst of same-session corrections (10 x +0.12/rewrite) pushes a
# fresh lesson 0 -> 0.90 in a single tick. 0.30 permits exactly one
# tier transition (INSTINCT->PATTERN 0.20, or PATTERN->RULE 0.30) but
# not two. See gap-analysis/01-internal-audit.md Gap 4 red-team note.
MAX_PER_SESSION_DELTA = 0.30

# Auto-detection threshold: if a session has more than this many corrections,
# it's likely machine-driven. Set high enough that intensive human sessions
# (code review, wrap-up, big lesson sweep) don't false-positive.
# Human sessions: typically 3-10 corrections. Machine: 30-60+.
_MACHINE_CORRECTION_THRESHOLD = 25

# Poisoning defense: if >40% of corrections in a category contradict each other,
# the correction stream may be compromised (intentional or accidental).
# 40% threshold: normal categories have <10% contradictions (style preferences
# are consistent). >40% means roughly half say "do X" and half say "don't do X".
_POISONING_CONTRADICTION_RATE = 0.40
_POISONING_MIN_CORRECTIONS = 4  # Need at least 4 corrections to detect pattern


def detect_correction_poisoning(corrections: list[dict]) -> list[str]:
    """Detect categories with suspiciously contradictory correction patterns.

    Returns list of category names where >40% of corrections contradict
    each other (e.g., one says "formalize" and another says "casualize").
    These categories should be treated with reduced confidence updates.
    """
    from collections import defaultdict

    by_category: dict[str, list[str]] = defaultdict(list)
    for c in corrections:
        cat = c.get("category", "").upper()
        desc = c.get("description", "")
        if cat and desc:
            by_category[cat].append(desc)

    poisoned: list[str] = []
    for cat, descs in by_category.items():
        if len(descs) < _POISONING_MIN_CORRECTIONS:
            continue
        # Check pairwise contradiction rate
        contradictions = 0
        comparisons = 0
        for i in range(len(descs)):
            for j in range(i + 1, min(i + 5, len(descs))):  # Cap at 5 per item to prevent O(n²)
                direction = _classify_correction_direction(descs[i], descs[j])
                comparisons += 1
                if direction == "CONTRADICTING":
                    contradictions += 1
        if comparisons > 0 and contradictions / comparisons >= _POISONING_CONTRADICTION_RATE:
            poisoned.append(cat)
            _log.warning(
                "Poisoning detected in %s: %.0f%% contradictions (%d/%d)",
                cat,
                contradictions / comparisons * 100,
                contradictions,
                comparisons,
            )
    return poisoned


def _detect_machine_context(
    corrections: list[dict],
    explicit: bool | None = None,
) -> bool:
    """Detect whether corrections are machine-driven.

    If ``explicit`` is True/False, use that directly. If None, auto-detect
    based on correction volume (> 25 corrections = machine context).
    """
    if explicit is not None:
        return explicit
    is_machine = len(corrections) > _MACHINE_CORRECTION_THRESHOLD
    if is_machine:
        import logging

        logging.getLogger(__name__).info(
            "Auto-detected machine context: %d corrections (threshold: %d)",
            len(corrections),
            _MACHINE_CORRECTION_THRESHOLD,
        )
    return is_machine


# Map diff_engine severity labels to graduation severity labels
_SEVERITY_MAP: dict[str, str] = {
    "as-is": "trivial",
    "discarded": "rewrite",
}

# Session-type → categories that are testable in that session type
# DRAFTING is immune during system sessions; ARCHITECTURE is immune during sales
CATEGORY_SESSION_MAP: dict[str, frozenset[str]] = {
    "full": frozenset(),  # empty = all categories testable
    "systems": frozenset(
        {
            "ARCHITECTURE",
            "PROCESS",
            "TOOL",
            "THOROUGHNESS",
            "CONTEXT",
        }
    ),
    "sales": frozenset(
        {
            "DRAFTING",
            "LEADS",
            "PRICING",
            "DEMO_PREP",
            "POSITIONING",
            "COMMUNICATION",
            "TONE",
            "ACCURACY",
            "DATA_INTEGRITY",
        }
    ),
}


def _normalize_severity(severity: str) -> str:
    """Map diff_engine labels to graduation labels."""
    return _SEVERITY_MAP.get(severity, severity)


def _is_testable(category: str, session_type: str) -> bool:
    """Check if a lesson category is testable in this session type."""
    allowed = CATEGORY_SESSION_MAP.get(session_type)
    if allowed is None or len(allowed) == 0:
        return True  # "full" or unknown session type: everything is testable
    return category.upper() in allowed


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_LESSON_RE = re.compile(
    r"\[(\d{4}-\d{2}-\d{2})\]\s+"
    r"\[(\w+):?([\d.]*)\]\s+"
    r"(\w[\w_/]*?):\s+"
    r"(.+)"
)

_META_RE = re.compile(
    r"Fire count:\s*(\d+)\s*\|\s*"
    r"Sessions since fire:\s*(\d+)\s*\|\s*"
    r"Misfires:\s*(\d+)"
)


def parse_lessons(text: str) -> list[Lesson]:
    """Parse lessons from the markdown format used in lessons.md.

    Format:
        [YYYY-MM-DD] [STATE:CONFIDENCE] CATEGORY: description
          Root cause: ...
          Fire count: N | Sessions since fire: N | Misfires: N

    Delegates parsing to the shared regex (same as meta_rules.py).
    """
    lessons: list[Lesson] = []
    lines = text.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        m = _LESSON_RE.match(line)
        if not m:
            i += 1
            continue

        date_str, state_str, conf_str, category, description = m.groups()

        state_map = {
            "INSTINCT": LessonState.INSTINCT,
            "PATTERN": LessonState.PATTERN,
            "RULE": LessonState.RULE,
            "UNTESTABLE": LessonState.UNTESTABLE,
            "KILLED": LessonState.KILLED,
            "ARCHIVED": LessonState.ARCHIVED,
        }
        state = state_map.get(state_str.upper(), LessonState.INSTINCT)
        if conf_str:
            confidence = float(conf_str)
        elif state == LessonState.RULE:
            confidence = 0.90
        elif state == LessonState.PATTERN:
            confidence = 0.70
        elif state in (LessonState.UNTESTABLE, LessonState.KILLED):
            confidence = 0.0
        else:
            confidence = 0.50

        # Extract root cause if inline
        root_cause = ""
        if "Root cause:" in description:
            parts = description.split("Root cause:", 1)
            description = parts[0].strip()
            root_cause = parts[1].strip()

        # Look ahead for metadata lines
        fire_count = 0
        sessions_since_fire = 0
        misfire_count = 0
        agent_type = ""
        kill_reason = ""
        correction_event_ids: list[str] = []
        pending_approval = False
        parent_meta_rule_id: str | None = None
        metadata_obj = None
        memory_ids: list[str] = []
        scope_json: str = ""
        domain_scores: dict = {}
        path = ""
        secondary_categories: list[str] = []
        climb_count = 0
        last_climb_session = 0
        tree_level = 0
        alpha = 1.0
        beta_param_val = 1.0
        j = i + 1
        while j < len(lines) and lines[j].startswith("  "):
            meta_line = lines[j].strip()
            if meta_line.startswith("Root cause:") and not root_cause:
                root_cause = meta_line[len("Root cause:") :].strip()
            elif meta_line.startswith("Agent:"):
                agent_type = meta_line[len("Agent:") :].strip()
            elif meta_line.startswith("Kill reason:"):
                kill_reason = meta_line[len("Kill reason:") :].strip()
            elif meta_line.startswith("Corrections:"):
                ids_str = meta_line[len("Corrections:") :].strip()
                correction_event_ids = [x.strip() for x in ids_str.split(",") if x.strip()]
            elif meta_line.startswith("Pending approval:"):
                pending_approval = meta_line[len("Pending approval:") :].strip().lower() == "yes"
            elif meta_line.startswith("Parent meta-rule:"):
                parent_meta_rule_id = meta_line[len("Parent meta-rule:") :].strip() or None
            elif meta_line.startswith("Memory links:"):
                memory_ids = [
                    x.strip()
                    for x in meta_line[len("Memory links:") :].strip().split(",")
                    if x.strip()
                ]
            elif meta_line.startswith("Scope:"):
                scope_json = meta_line[len("Scope:") :].strip()
            elif meta_line.startswith("Beta params:"):
                import json as _json_bp

                try:
                    bp = _json_bp.loads(meta_line[len("Beta params:") :].strip())
                    alpha = bp.get("alpha", 1.0)
                    beta_param_val = bp.get("beta", 1.0)
                except _json_bp.JSONDecodeError:
                    pass
            elif meta_line.startswith("Domain scores:"):
                import json as _json

                try:
                    domain_scores = _json.loads(meta_line[len("Domain scores:") :].strip())
                except _json.JSONDecodeError:
                    domain_scores = {}
            elif meta_line.startswith("Path:"):
                path = meta_line[len("Path:") :].strip()
            elif meta_line.startswith("Secondary categories:"):
                secondary_categories = [
                    x.strip()
                    for x in meta_line[len("Secondary categories:") :].strip().split(",")
                    if x.strip()
                ]
            elif meta_line.startswith("Climb:"):
                import json as _json_cl

                try:
                    _cl = _json_cl.loads(meta_line[len("Climb:") :].strip())
                    climb_count = _cl.get("count", 0)
                    last_climb_session = _cl.get("last_session", 0)
                    tree_level = _cl.get("level", 0)
                except _json_cl.JSONDecodeError:
                    pass
            elif meta_line.startswith("Metadata:"):
                import json as _json_md

                try:
                    _md_dict = _json_md.loads(meta_line[len("Metadata:") :].strip())
                    from gradata._types import RuleMetadata as _RM

                    metadata_obj = _RM(
                        **{k: v for k, v in _md_dict.items() if k in _RM.__dataclass_fields__}
                    )
                except (ValueError, TypeError, _json_md.JSONDecodeError):
                    metadata_obj = None
            meta_m = _META_RE.search(meta_line)
            if meta_m:
                fire_count = int(meta_m.group(1))
                sessions_since_fire = int(meta_m.group(2))
                misfire_count = int(meta_m.group(3))
            j += 1

        _lesson = Lesson(
            date=date_str,
            state=state,
            confidence=confidence,
            category=category.upper(),
            description=description.rstrip(),
            root_cause=root_cause,
            fire_count=fire_count,
            sessions_since_fire=sessions_since_fire,
            misfire_count=misfire_count,
            scope_json=scope_json,
            agent_type=agent_type,
            kill_reason=kill_reason,
            correction_event_ids=correction_event_ids,
            pending_approval=pending_approval,
            parent_meta_rule_id=parent_meta_rule_id,
            memory_ids=memory_ids,
            domain_scores=domain_scores,
            alpha=alpha,
            beta_param=beta_param_val,
            path=path,
            secondary_categories=secondary_categories,
            climb_count=climb_count,
            last_climb_session=last_climb_session,
            tree_level=tree_level,
        )
        if metadata_obj is not None:
            _lesson.metadata = metadata_obj
        lessons.append(_lesson)
        i = j if j > i + 1 else i + 1

    return lessons


# ---------------------------------------------------------------------------
# FSRS-Inspired Confidence Functions
# ---------------------------------------------------------------------------
# Spaced repetition insight: bonuses shrink as confidence rises (diminishing
# returns), penalties shrink as confidence drops (floor protection).
# This prevents runaway confidence and makes the 0.90 RULE threshold genuinely
# hard to reach — requires sustained, repeated success.


def fsrs_bonus(confidence: float, *, machine: bool = False) -> float:
    """Confidence-dependent survival bonus (FSRS-inspired).

    Higher confidence → smaller bonus (diminishing returns).
    At confidence 0.30: ~0.08. At 0.80: ~0.06. At 0.95: ~0.05.

    In machine mode, uses MACHINE_ACCEPTANCE_BONUS with flatter curve
    (0.3 damping instead of 0.5) so bonuses stay meaningful at high volume.
    """
    base = MACHINE_ACCEPTANCE_BONUS if machine else ACCEPTANCE_BONUS
    damping = 0.3 if machine else 0.5
    return round(base * (1.0 - confidence * damping), 4)


def fsrs_penalty(confidence: float, *, machine: bool = False) -> float:
    """Confidence-dependent contradiction penalty (FSRS-inspired).

    Higher confidence → larger penalty (more to lose).
    Uses quadratic scaling: penalty grows faster at higher confidence levels,
    enabling faster preference reversal for established rules.

    In machine mode, uses halved base penalty so high-volume corrections
    don't collapse confidence in 4 rounds.
    """
    base = abs(MACHINE_CONTRADICTION_PENALTY) if machine else abs(CONTRADICTION_PENALTY)
    # Quadratic scaling: steeper at high confidence for faster reversal
    # At 0.30: base * 0.572, at 0.75: base * 1.063, at 0.90: base * 1.229
    return round(base * (0.5 + confidence * confidence * 0.8), 4)


# ---------------------------------------------------------------------------
# Bayesian Confidence Blending
# ---------------------------------------------------------------------------

_BAYESIAN_BLEND_MIN_OBS = 5
_BAYESIAN_BLEND_MAX_OBS = 20


def _bayesian_blend_weight(total_observations: int) -> float:
    """Return weight for Bayesian component [0.0, 0.7]."""
    if total_observations < _BAYESIAN_BLEND_MIN_OBS:
        return 0.0
    if total_observations >= _BAYESIAN_BLEND_MAX_OBS:
        return 0.7
    return (
        0.7
        * (total_observations - _BAYESIAN_BLEND_MIN_OBS)
        / (_BAYESIAN_BLEND_MAX_OBS - _BAYESIAN_BLEND_MIN_OBS)
    )


def _bayesian_confidence(lesson: Lesson) -> float:
    """Compute blended confidence from beta posterior + FSRS."""
    from gradata._stats import beta_posterior

    total_obs = int(lesson.alpha + lesson.beta_param - 2)
    blend_w = _bayesian_blend_weight(total_obs)

    if blend_w == 0.0:
        return lesson.confidence

    post = beta_posterior(
        successes=max(0, int(lesson.alpha - 1)),
        trials=max(0, total_obs),
    )
    bayesian_conf = post["posterior_mean"]
    return round(blend_w * bayesian_conf + (1.0 - blend_w) * lesson.confidence, 2)


# ---------------------------------------------------------------------------
# Correction Direction Detection
# ---------------------------------------------------------------------------


def _classify_correction_direction(
    correction_desc: str,
    lesson_desc: str,
) -> str:
    """Classify whether a correction reinforces or contradicts a lesson.

    Uses keyword overlap and polarity/negation/sentiment detection from
    the contradiction_detector module to determine direction.

    Returns: "REINFORCING", "CONTRADICTING", or "UNKNOWN"
    """
    if not correction_desc or not lesson_desc:
        return "UNKNOWN"

    try:
        from gradata.enhancements.contradiction_detector import (
            _check_negation,
            _check_opposite_sentiment,
            _check_polarity,
            _extract_topic_words,
            _normalize,
        )
    except ImportError:
        return "UNKNOWN"

    corr_norm = _normalize(correction_desc)
    lesson_norm = _normalize(lesson_desc)

    corr_topics = _extract_topic_words(correction_desc)
    lesson_topics = _extract_topic_words(lesson_desc)

    # Must share at least one topic word to be related
    overlap = corr_topics & lesson_topics
    if not overlap:
        return "UNKNOWN"

    # Check for contradiction signals
    polarity = _check_polarity(corr_norm, lesson_norm)
    negation = _check_negation(corr_norm, lesson_norm)
    sentiment = _check_opposite_sentiment(corr_norm, lesson_norm)

    max_contradiction = max(polarity, negation, sentiment)

    if max_contradiction >= 0.5:
        return "CONTRADICTING"

    # Shared topics + no contradiction = reinforcing
    overlap_ratio = len(overlap) / max(1, min(len(corr_topics), len(lesson_topics)))
    if overlap_ratio >= 0.3:
        return "REINFORCING"

    return "UNKNOWN"


# ---------------------------------------------------------------------------
# Confidence Scoring
# ---------------------------------------------------------------------------


def update_confidence(
    lessons: list[Lesson],
    corrections_this_session: list[dict] | None = None,
    *,
    severity_data: dict[str, str] | None = None,
    session_type: str = "full",
    maturity: str = "INFANT",
    renter: bool = False,
    machine_mode: bool | None = None,
    salt: str = "",
    injected_lesson_keys: set[str] | None = None,
) -> list[Lesson]:
    """Update confidence for each lesson based on session corrections.

    Mutates lessons in-place, runs graduation, and returns the list.

    Behavior:
      - Zero corrections: no confidence changes (can't evaluate without signal)
      - Category contradicted: apply FSRS penalty (confidence-dependent)
      - Category survived (corrections exist in OTHER categories): apply FSRS bonus
      - Misfire: apply MISFIRE_PENALTY

    Also handles:
      - sessions_since_fire tracking
      - UNTESTABLE detection (20+ sessions with fire_count==0)
      - Inline graduation (promote/demote based on updated confidence)

    Args:
        lessons: Active lessons to update.
        corrections_this_session: List of correction dicts, each with at
            least a "category" key. Optional "misfired" key for misfire signal.
        severity_data: Dict mapping category -> severity label for the session.
            When absent, defaults to "moderate" for backward compat.
        session_type: "full", "systems", or "sales". Controls which
            categories are testable (session-type-aware decay).
        maturity: Brain maturity phase for kill-switch thresholds.
        renter: If True, skip all confidence mutations (renter mode).
        machine_mode: If None, auto-detect from correction volume (>10 = machine).
            If True/False, override auto-detection. Machine mode uses softer
            penalties and higher kill limits for high-volume correction contexts.
        injected_lesson_keys: Optional set of "CATEGORY:description[:60]" keys
            (same key format as _core._lesson_key) identifying lessons that
            were actually injected into the session prompt. The per-lesson
            attribute ``_was_injected_this_session`` is also honoured for
            callers that prefer to mark evidence inline. When neither signal
            is present for a surviving lesson, the confidence bonus is still
            applied but ``fire_count`` is NOT incremented — this preserves
            the "no promotion from silence" invariant documented on
            ``graduate()`` (see gap-analysis/01-internal-audit.md #1.10).
    """
    if renter:
        return lessons

    corrections = corrections_this_session or []
    severity_data = severity_data or {}

    # Poisoning defense: detect categories with contradictory corrections
    poisoned_categories = set(detect_correction_poisoning(corrections))

    # Detect machine context and select effective constants
    is_machine = _detect_machine_context(corrections, machine_mode)
    eff_severity = MACHINE_SEVERITY_WEIGHTS if is_machine else SEVERITY_WEIGHTS
    eff_kill_limits = MACHINE_KILL_LIMITS if is_machine else KILL_LIMITS

    # Build set of corrected categories this session
    corrected_categories: set[str] = set()
    misfired_categories: set[str] = set()
    # Auto-build severity_data from inline severity_label if not provided
    inline_severity: dict[str, str] = {}
    for c in corrections:
        cat = c.get("category", "").upper()
        if cat:
            corrected_categories.add(cat)
        if c.get("misfired"):
            misfired_categories.add(cat)
        if cat and "severity_label" in c and cat not in severity_data:
            inline_severity[cat] = c["severity_label"]

    # Merge inline severity into severity_data
    if inline_severity:
        severity_data = {**severity_data, **inline_severity}

    kill_limit = eff_kill_limits.get(maturity, eff_kill_limits["INFANT"])

    for lesson in lessons:
        # Skip terminal states
        if lesson.state in (LessonState.KILLED, LessonState.ARCHIVED):
            continue

        # Snapshot pre-session state for the per-session invariant enforced
        # below. graduate() also reads _pre_session_confidence to emit its
        # safety-jump warning; setting it here makes update_confidence the
        # single source of truth.
        # Invariant (gap-analysis/01-internal-audit.md Gap 4 red-team note):
        # a single session can at most cause ONE graduation tier transition
        # and ONE MAX_PER_SESSION_DELTA-sized move in confidence. Blocks the
        # Sybil scenario where 10 coordinated corrections push a fresh
        # lesson 0 -> RULE in a single tick.
        if not hasattr(lesson, "_pre_session_confidence"):
            lesson._pre_session_confidence = lesson.confidence  # type: ignore[attr-defined]
            lesson._pre_session_state = lesson.state  # type: ignore[attr-defined]

        cat = lesson.category.upper()

        # Session-type immunity: skip lessons whose category isn't testable
        if not _is_testable(cat, session_type):
            continue

        # Poisoning defense: skip confidence updates for compromised categories
        if cat in poisoned_categories:
            continue

        # Only adjust confidence when there are corrections to evaluate against
        if corrections:
            if cat in misfired_categories:
                # Misfire: rule was irrelevant (worse than contradiction)
                lesson.confidence = round(
                    max(0.0, min(1.0, lesson.confidence + MISFIRE_PENALTY)), 2
                )
                lesson.misfire_count += 1
            elif cat in corrected_categories:
                # Determine direction: does this correction reinforce or contradict?
                direction = "UNKNOWN"
                for c in corrections:
                    c_cat = c.get("category", "").upper()
                    if c_cat == cat:
                        # Honor explicit direction if provided (e.g. from hooks)
                        explicit = c.get("direction", "").upper()
                        if explicit in ("REINFORCING", "CONTRADICTING"):
                            direction = explicit
                        else:
                            c_desc = c.get("description", "")
                            if c_desc and lesson.description:
                                direction = _classify_correction_direction(
                                    c_desc, lesson.description
                                )
                        break

                if direction == "REINFORCING":
                    # Reinforcing: correction aligns with lesson direction → BONUS
                    lesson.alpha += 1.0
                    # Reset contradiction streak on reinforcement
                    lesson._contradiction_streak = 0
                    base_bonus = fsrs_bonus(lesson.confidence, machine=is_machine)
                    if cat in severity_data:
                        raw_severity = severity_data[cat]
                        severity = _normalize_severity(raw_severity)
                        weight = eff_severity.get(severity, eff_severity["moderate"])
                        bonus = base_bonus * weight
                    else:
                        bonus = base_bonus
                    _pre_bonus_conf = lesson.confidence
                    lesson.confidence = round(max(0.0, min(1.0, lesson.confidence + bonus)), 2)
                    # Monotonicity: on a reinforcement event, the Bayesian
                    # blend cannot pull confidence DOWN. Mirrors the symmetric
                    # penalty-path guard. See gap-analysis/01-internal-audit.md
                    # #1.3.
                    _bayes = max(0.0, min(1.0, _bayesian_confidence(lesson)))
                    lesson.confidence = max(_bayes, _pre_bonus_conf)
                    lesson.fire_count += 1
                else:
                    # CONTRADICTING or UNKNOWN: FSRS penalty
                    lesson.beta_param += 1.0
                    base_penalty = fsrs_penalty(lesson.confidence, machine=is_machine)
                    if cat in severity_data:
                        raw_severity = severity_data[cat]
                        severity = _normalize_severity(raw_severity)
                        weight = eff_severity.get(severity, eff_severity["moderate"])
                        penalty = base_penalty * weight
                    else:
                        penalty = base_penalty
                    # Explicit contradictions get accelerated penalty
                    # Streak tracking: consecutive contradictions hit harder
                    if direction == "CONTRADICTING":
                        streak = getattr(lesson, "_contradiction_streak", 0) + 1
                        lesson._contradiction_streak = streak
                        streak_mult = 1.0 + CONTRADICTION_STREAK_STEP * (streak - 1)
                        # Severity-aware boost for contradictions
                        sev_boost = CONTRADICTION_SEVERITY_BOOST.get(
                            severity if cat in severity_data else "moderate",
                            1.0,
                        )
                        penalty *= CONTRADICTION_ACCELERATION * streak_mult * sev_boost
                        # RULE-state override: when user explicitly contradicts
                        # a proven rule, they're intentionally overriding it.
                        # Apply additional 20% penalty for RULE-state lessons.
                        if lesson.state == LessonState.RULE:
                            penalty *= 1.2
                    else:
                        # Reset streak on non-contradicting correction
                        lesson._contradiction_streak = 0
                    # Preferences decay slower — stable user taste signals
                    # But skip damping when user explicitly contradicts the
                    # preference (they're intentionally reversing it)
                    if (
                        lesson.correction_type == CorrectionType.PREFERENCE
                        and direction != "CONTRADICTING"
                    ):
                        penalty *= PREFERENCE_DECAY_DAMPER
                    # Cap compound penalty. Without this, a single rewrite
                    # contradiction on a RULE can subtract ~0.63 in one step;
                    # see gap-analysis/01-internal-audit.md #1.3 and the
                    # MAX_PER_STEP_PENALTY comment at module top.
                    penalty = min(penalty, MAX_PER_STEP_PENALTY)
                    _pre_penalty_conf = lesson.confidence
                    lesson.confidence = round(max(0.0, min(1.0, lesson.confidence - penalty)), 2)
                    # Single principled update rule: FSRS-then-blend. We take
                    # the Bayesian posterior as a second opinion but enforce
                    # monotonicity on penalty events — the blend cannot pull
                    # confidence UP after a correction. Without this guard
                    # the two update paths (FSRS and Bayesian) overwrite
                    # each other and oscillate under alternating corrections
                    # (audit finding gap-analysis/01-internal-audit.md #1.3).
                    _bayes = max(0.0, min(1.0, _bayesian_confidence(lesson)))
                    lesson.confidence = min(_bayes, _pre_penalty_conf)
            else:
                # Survived: category was testable, corrections exist elsewhere
                # Cooling period: skip survival bonus if recently contradicted
                streak = getattr(lesson, "_contradiction_streak", 0)
                if streak >= CONTRADICTION_COOLING_SESSIONS:
                    continue
                base_bonus = fsrs_bonus(lesson.confidence, machine=is_machine)
                if severity_data:
                    # Scale survival by severity of corrections elsewhere:
                    # trivial corrections = weak evidence of survival
                    sev_values = [
                        SURVIVAL_SEVERITY_WEIGHTS.get(
                            _normalize_severity(v),
                            SURVIVAL_SEVERITY_WEIGHTS["moderate"],
                        )
                        for k, v in severity_data.items()
                        if k.upper() != cat
                    ]
                    if sev_values:
                        avg_weight = sum(sev_values) / len(sev_values)
                        bonus = base_bonus * avg_weight
                    else:
                        bonus = base_bonus
                else:
                    bonus = base_bonus
                lesson.confidence = round(max(0.0, min(1.0, lesson.confidence + bonus)), 2)
                # Gate fire_count increment on evidence of actual injection.
                # gap-analysis/01-internal-audit.md #1.10: auto-incrementing
                # fire_count on "survived" bypasses the no-promotion-from-silence
                # gate asserted in graduate(). Without injection evidence we
                # still apply the confidence bonus (legacy behaviour) but leave
                # fire_count untouched so promotion remains gated on real fires.
                lesson_key = f"{lesson.category.upper()}:{lesson.description[:60]}"
                was_injected = bool(
                    getattr(lesson, "_was_injected_this_session", False)
                    or (injected_lesson_keys and lesson_key in injected_lesson_keys)
                )
                if was_injected:
                    lesson.fire_count += 1
                    lesson.sessions_since_fire = 0

        # Track sessions since fire
        lesson.sessions_since_fire += 1

        # Inline UNTESTABLE detection
        if (
            lesson.fire_count == 0
            and lesson.sessions_since_fire >= kill_limit
            and lesson.state
            not in (LessonState.UNTESTABLE, LessonState.KILLED, LessonState.ARCHIVED)
        ):
            lesson.state = LessonState.UNTESTABLE

    # Enforce per-session delta invariant BEFORE graduation evaluates
    # state transitions. A session can move confidence by at most
    # MAX_PER_SESSION_DELTA (0.30), which permits exactly one tier
    # transition (INSTINCT->PATTERN spans 0.20, PATTERN->RULE spans 0.30)
    # but blocks the Sybil scenario where coordinated corrections chain
    # two transitions in a single tick. See module-top comment and
    # gap-analysis/01-internal-audit.md Gap 4.
    for lesson in lessons:
        if lesson.state in (LessonState.KILLED, LessonState.ARCHIVED):
            continue
        pre = getattr(lesson, "_pre_session_confidence", None)
        if isinstance(pre, (int, float)):
            low = max(0.0, pre - MAX_PER_SESSION_DELTA)
            high = min(1.0, pre + MAX_PER_SESSION_DELTA)
            clamped = max(low, min(high, lesson.confidence))
            if clamped != lesson.confidence:
                _log.debug(
                    "Per-session delta cap: %s %.2f->%.2f clamped from %.2f (pre=%.2f)",
                    lesson.category,
                    pre,
                    clamped,
                    lesson.confidence,
                    pre,
                )
                lesson.confidence = round(clamped, 2)

    # Inline promotion/demotion after confidence updates
    # (UNTESTABLE detection already handled above — don't re-run
    # full graduate() which would kill newly-flagged UNTESTABLE lessons)
    # Use salted thresholds consistent with graduate()
    if salt:
        from gradata.security.brain_salt import salt_threshold

        _uc_pattern_thr = salt_threshold(PATTERN_THRESHOLD, salt, "PATTERN")
        _uc_rule_thr = salt_threshold(RULE_THRESHOLD, salt, "RULE")
    else:
        _uc_pattern_thr = PATTERN_THRESHOLD
        _uc_rule_thr = RULE_THRESHOLD

    for lesson in lessons:
        if lesson.state in (LessonState.KILLED, LessonState.ARCHIVED, LessonState.UNTESTABLE):
            continue
        # Per-session tier cap: at most one graduation tier transition
        # per session, regardless of supporting corrections. If the
        # lesson already moved in this session, block the next move.
        pre_state = getattr(lesson, "_pre_session_state", None)
        already_transitioned = pre_state is not None and pre_state != lesson.state
        # Promote PATTERN -> RULE
        if (
            not already_transitioned
            and lesson.state == LessonState.PATTERN
            and lesson.confidence >= _uc_rule_thr
            and lesson.fire_count >= MIN_APPLICATIONS_FOR_RULE
        ) or (
            not already_transitioned
            and lesson.state == LessonState.INSTINCT
            and lesson.confidence >= _uc_pattern_thr
            and lesson.fire_count >= MIN_APPLICATIONS_FOR_PATTERN
        ):
            lesson.state = transition(lesson.state, "promote")
        # Demote PATTERN -> INSTINCT
        elif (
            not already_transitioned
            and lesson.state == LessonState.PATTERN
            and lesson.confidence < _uc_pattern_thr
        ):
            lesson.state = transition(lesson.state, "demote")

    return lessons


# ---------------------------------------------------------------------------
# Graduation
# ---------------------------------------------------------------------------


def _passes_beta_lb_gate(lesson: Lesson) -> bool:
    """Beta lower-bound gate on PATTERN -> RULE promotion.

    Opt-in via env var ``GRADATA_BETA_LB_GATE`` (default off). When enabled,
    requires the 5th-percentile lower bound of Beta(α, β) to meet the
    configured threshold (``GRADATA_BETA_LB_THRESHOLD``, default 0.70) AND
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

    try:
        threshold = float(os.environ.get("GRADATA_BETA_LB_THRESHOLD", "0.70"))
        min_fires = int(os.environ.get("GRADATA_BETA_LB_MIN_FIRES", "5"))
    except ValueError:
        threshold, min_fires = 0.70, 5

    if lesson.fire_count < min_fires:
        return False

    alpha = getattr(lesson, "alpha", 1.0)
    beta_param = getattr(lesson, "beta_param", 1.0)
    from gradata.rules.rule_engine import _beta_ppf_05

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
        from gradata.security.brain_salt import salt_threshold

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
            elif lesson.state in (LessonState.INSTINCT, LessonState.PATTERN):
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
                from gradata.enhancements.similarity import semantic_similarity

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
                    from gradata.enhancements.similarity import semantic_similarity

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
                from gradata.contrib.patterns.tree_of_thoughts import evaluate_rule_candidates

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
                from gradata.enhancements import rule_to_hook

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
        if (
            not block_promotion
            and lesson.state == LessonState.INSTINCT
            and lesson.confidence >= eff_pattern_threshold
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


def propagate_confidence(
    lessons: list[Lesson],
    meta_rules: list,
) -> list:
    """Update meta-rule confidence from weighted average of source lessons.

    Each meta-rule's confidence becomes the mean confidence of its source
    lessons (matched by parent_meta_rule_id).  Meta-rules with no matching
    lessons keep their current confidence.

    Args:
        lessons: All lessons (may include non-source lessons).
        meta_rules: List of MetaRule objects to update in-place.

    Returns:
        The same meta_rules list, updated.
    """
    # Build lookup: meta_rule_id -> list of source lesson confidences
    by_meta: dict[str, list[float]] = {}
    for lesson in lessons:
        mid = lesson.parent_meta_rule_id
        if mid:
            by_meta.setdefault(mid, []).append(lesson.confidence)

    for meta in meta_rules:
        confs = by_meta.get(meta.id)
        if confs:
            meta.confidence = round(sum(confs) / len(confs), 2)

    return meta_rules


# ---------------------------------------------------------------------------
# Maturity phase helpers
# ---------------------------------------------------------------------------


def get_maturity_phase(total_sessions: int) -> str:
    """Determine brain maturity phase from total session count.

    INFANT (<50):    fresh brain, high correction rate expected
    ADOLESCENT (<100): patterns forming, lessons graduating
    MATURE (<200):   stable rules, meta-rules emerging
    STABLE (200+):   compound learning, minimal new instincts
    """
    if total_sessions < 50:
        return "INFANT"
    elif total_sessions < 100:
        return "ADOLESCENT"
    elif total_sessions < 200:
        return "MATURE"
    else:
        return "STABLE"


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def format_lessons(lessons: list[Lesson]) -> str:
    """Serialize lessons to the lessons.md markdown format.

    Round-trip property: parse_lessons(format_lessons(lessons)) ≈ lessons
    """
    lines: list[str] = []

    for lesson in lessons:
        # Skip terminal states
        if lesson.state in (LessonState.KILLED, LessonState.ARCHIVED):
            continue

        header = (
            f"[{lesson.date}] [{lesson.state.value}:{lesson.confidence:.2f}] "
            f"{lesson.category}: {lesson.description}"
        )
        lines.append(header)

        if lesson.root_cause:
            lines.append(f"  Root cause: {lesson.root_cause}")

        if lesson.fire_count or lesson.sessions_since_fire or lesson.misfire_count:
            lines.append(
                f"  Fire count: {lesson.fire_count} | "
                f"Sessions since fire: {lesson.sessions_since_fire} | "
                f"Misfires: {lesson.misfire_count}"
            )

        if lesson.agent_type:
            lines.append(f"  Agent: {lesson.agent_type}")

        if lesson.kill_reason:
            lines.append(f"  Kill reason: {lesson.kill_reason}")

        if lesson.correction_event_ids:
            lines.append(f"  Corrections: {','.join(lesson.correction_event_ids)}")

        if lesson.pending_approval:
            lines.append("  Pending approval: yes")

        if lesson.parent_meta_rule_id:
            lines.append(f"  Parent meta-rule: {lesson.parent_meta_rule_id}")

        if lesson.memory_ids:
            lines.append(f"  Memory links: {','.join(lesson.memory_ids)}")

        if lesson.scope_json:
            lines.append(f"  Scope: {lesson.scope_json}")

        if lesson.domain_scores:
            import json as _json

            lines.append(f"  Domain scores: {_json.dumps(lesson.domain_scores)}")

        if lesson.alpha != 1.0 or lesson.beta_param != 1.0:
            import json as _json_bp

            lines.append(
                f"  Beta params: {_json_bp.dumps({'alpha': lesson.alpha, 'beta': lesson.beta_param})}"
            )

        if lesson.path:
            lines.append(f"  Path: {lesson.path}")

        if lesson.secondary_categories:
            lines.append(f"  Secondary categories: {','.join(lesson.secondary_categories)}")

        if lesson.climb_count or lesson.last_climb_session or lesson.tree_level:
            import json as _json_cl

            lines.append(
                f"  Climb: {_json_cl.dumps({'count': lesson.climb_count, 'last_session': lesson.last_climb_session, 'level': lesson.tree_level})}"
            )

        if hasattr(lesson, "metadata") and lesson.metadata is not None:
            import json as _json_meta

            md = lesson.metadata.to_dict() if hasattr(lesson.metadata, "to_dict") else {}
            if any(v for v in md.values() if v and v != 0.5):  # only write non-default
                lines.append(f"  Metadata: {_json_meta.dumps(md)}")

        lines.append("")  # blank line between lessons

    return "\n".join(lines).rstrip() + "\n" if lines else ""


# ---------------------------------------------------------------------------
# Learning Velocity
# ---------------------------------------------------------------------------


def compute_learning_velocity(
    lessons: list[Lesson],
    window: int = 10,
) -> dict:
    """Measure how fast the brain is adapting.

    Returns a dict with:
      - graduation_rate: ratio of RULE lessons to total (higher = more graduated)
      - total_lessons: count of all lessons provided
      - state_distribution: dict of state -> count
      - correction_categories: dict of category -> count
    """
    if not lessons:
        return {
            "graduation_rate": 0.0,
            "total_lessons": 0,
            "state_distribution": {},
            "correction_categories": {},
        }

    total = len(lessons)
    rules = sum(1 for l in lessons if l.state == LessonState.RULE)

    state_dist: dict[str, int] = {}
    cat_dist: dict[str, int] = {}
    for l in lessons:
        state_dist[l.state.value] = state_dist.get(l.state.value, 0) + 1
        cat_dist[l.category] = cat_dist.get(l.category, 0) + 1

    # Estimate avg time to rule (sessions_since_fire as proxy for lesson age)
    rule_lessons = [l for l in lessons if l.state == LessonState.RULE]
    avg_time = (
        sum(l.fire_count + l.sessions_since_fire for l in rule_lessons) / len(rule_lessons)
        if rule_lessons
        else 0.0
    )

    return {
        "graduation_rate": round(rules / total, 3) if total else 0.0,
        "total_lessons": total,
        "state_distribution": state_dist,
        "correction_categories": cat_dist,
        "avg_time_to_rule": round(avg_time, 1),
    }
