"""
Self-Improvement Pipeline — INSTINCT -> PATTERN -> RULE
=========================================================
SDK LAYER: Pure logic, no file I/O. Caller reads/writes files,
this module transforms structured lesson data.

The pipeline:
  1. User corrects the brain -> CORRECTION event with category tag
  2. Correction becomes a LESSON at confidence 0.30 (INSTINCT)
  3. Each session survived without contradiction: confidence += 0.10
  4. At 0.60: promotes to PATTERN — REQUIRES fire_count >= 3
  5. At 0.90: graduates to RULE — REQUIRES fire_count >= 5
  6. Contradicted: confidence -= 0.20
  7. Misfired (applied but made output worse): confidence -= 0.25
  8. Accepted application: fire_count += 1, confidence += 0.05
  9. 0 fires after 20 sessions: flagged UNTESTABLE
"""

from __future__ import annotations

import re
from dataclasses import dataclass  # noqa: F401 — used by downstream importers
from enum import Enum  # noqa: F401 — used by downstream importers

# Types live in _types.py (Layer 0) so patterns/ can import without
# reaching into enhancements/.  Re-export here for backward compat.
from gradata._types import Lesson, LessonState  # noqa: F401


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INITIAL_CONFIDENCE = 0.30
# FSRS-inspired power-law parameters (Piotr Wozniak, 2024).
# Replaces linear SM-2-style increments with stability-dependent updates.
# Key insight: a lesson at 0.30 should gain more per session than one at 0.80.
# Formula: bonus = BASE_BONUS * (1 - current_confidence) ^ DECAY_EXPONENT
# At 0.30: bonus = 0.15 * 0.70^0.6 = ~0.12 (fast early growth)
# At 0.80: bonus = 0.15 * 0.20^0.6 = ~0.05 (slow near ceiling)
FSRS_BASE_BONUS = 0.15        # Maximum possible bonus per session
FSRS_DECAY_EXPONENT = 0.6     # Power-law exponent (higher = steeper drop-off)
FSRS_PENALTY_MULTIPLIER = 2.0 # Penalties are 2x the bonus at current confidence

# Legacy linear constants (kept for backward compatibility / renter mode)
SURVIVAL_BONUS = 0.10
ACCEPTANCE_BONUS = 0.05
CONTRADICTION_PENALTY = 0.20
MISFIRE_PENALTY = 0.25

PATTERN_THRESHOLD = 0.60
RULE_THRESHOLD = 0.90
UNTESTABLE_SESSION_LIMIT = 20

# Kill switch thresholds by brain maturity phase (SPEC Section 1).
# Counts RELEVANT cycles only — sessions where the lesson's category was active.
# A DRAFTING lesson ignores system/build sessions entirely.
# Thresholds are conservative to protect compound knowledge.
KILL_SWITCH_BY_MATURITY = {
    "INFANT": 15,       # Sessions 0-50: very lenient, brain still exploring
    "ADOLESCENT": 12,   # Sessions 50-100: moderate, lessons had time to prove value
    "MATURE": 10,       # Sessions 100-200: lessons should fire if relevant
    "STABLE": 8,        # Sessions 200+: still generous — proven lessons are the product
}

# Brain usage modes — affects kill switch behavior
BRAIN_MODE_OWNER = "owner"      # Training mode: kill switches active
BRAIN_MODE_RENTER = "renter"    # Using mode: lessons frozen, no auto-kills


def fsrs_bonus(current_confidence: float) -> float:
    """Compute FSRS-inspired stability-dependent confidence bonus.

    Unlike linear SM-2-style increments (+0.10 regardless of current level),
    this uses a power-law curve where low-confidence lessons gain more per
    session than high-confidence ones. Mirrors FSRS's stability-dependent
    interval scheduling.

    Returns a value in ~[0.006, 0.15] depending on current confidence.
    At 0.30: ~0.12. At 0.80: ~0.05. At 0.99: ~0.006.

    Reference: FSRS Algorithm (open-spaced-repetition, 2024).
    """
    headroom = max(0.01, 1.0 - current_confidence)
    return round(FSRS_BASE_BONUS * (headroom ** FSRS_DECAY_EXPONENT), 4)


def fsrs_penalty(current_confidence: float) -> float:
    """Compute FSRS-inspired stability-dependent confidence penalty.

    Penalty is proportional to the bonus at current confidence, scaled
    by FSRS_PENALTY_MULTIPLIER (default 2x). This ensures the penalty/reward
    ratio stays consistent across the confidence range, unlike fixed
    penalties that over-punish low-confidence lessons.
    """
    return round(fsrs_bonus(current_confidence) * FSRS_PENALTY_MULTIPLIER, 4)


def get_maturity_phase(total_sessions: int) -> str:
    """Determine brain maturity phase from total session count."""
    if total_sessions < 50:
        return "INFANT"
    elif total_sessions < 100:
        return "ADOLESCENT"
    elif total_sessions < 200:
        return "MATURE"
    else:
        return "STABLE"


def get_kill_switch_threshold(total_sessions: int) -> int:
    """Get the kill switch threshold for the brain's current maturity phase.

    Returns the number of RELEVANT cycles (not total sessions) after which
    a zero-fire lesson is flagged UNTESTABLE. "Relevant" means sessions
    where the lesson's category was active (e.g., DRAFTING lessons only
    count sessions that had drafting work, not system/build sessions).
    """
    phase = get_maturity_phase(total_sessions)
    return KILL_SWITCH_BY_MATURITY.get(phase, UNTESTABLE_SESSION_LIMIT)

# Minimum real applications before a lesson can promote tiers
# Evidence-based: Bayesian posterior > 0.6 after 3 successes (Beta(1,1) prior).
# Few-shot learning: 3-5 examples for reliable generalization with strong prior.
# Real data: 13 categories across 41 corrections = ~3 per category per 44 sessions.
MIN_APPLICATIONS_FOR_PATTERN = 3   # 3+ fires across 3+ sessions (Bayesian threshold)
MIN_APPLICATIONS_FOR_RULE = 5      # 5+ fires (5-shot standard, posterior > 0.90)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

# Matches:
#   [2026-03-20] [PATTERN:0.80:12] CATEGORY: description text   (new format with fires)
#   [2026-03-20] [PATTERN:0.80]    CATEGORY: description text   (old format, no fires)
#   [2026-03-20] [RULE]            CATEGORY: description text   (old rule format)
#   [2026-03-20] [RULE:0.95:7]     CATEGORY: description text   (new rule format)
_LESSON_RE = re.compile(
    r"^\[(\d{4}-\d{2}-\d{2})\]\s+"
    r"\[(INSTINCT|PATTERN|RULE|UNTESTABLE)"
    r"(?::(\d+\.\d+))??"          # optional confidence
    r"(?::(\d+))?\]\s+"           # optional fire_count (only present if confidence also present)
    r"(\w+):\s*(.+)",
    re.DOTALL,
)

_ROOT_CAUSE_RE = re.compile(r"Root cause:\s*(.+)", re.IGNORECASE)


def parse_lessons(text: str) -> list[Lesson]:
    """Parse a lessons.md file into structured Lesson objects.

    Handles both the legacy format and the new format with fire_count:

    Legacy:
        [DATE] [STATE:CONFIDENCE] CATEGORY: description. Root cause: ...
        [DATE] [RULE] CATEGORY: description

    New:
        [DATE] [STATE:CONFIDENCE:FIRES] CATEGORY: description. Root cause: ...
        [DATE] [RULE:0.90:7] CATEGORY: description

    Lines that don't match the lesson format (headers, comments, blanks)
    are silently skipped.

    Backward compatible: old-format files parse correctly with fire_count=0.
    """
    lessons: list[Lesson] = []

    for line in text.split("\n"):
        line = line.strip()
        m = _LESSON_RE.match(line)
        if not m:
            continue

        date_str = m.group(1)
        state_str = m.group(2)
        conf_str = m.group(3)
        fires_str = m.group(4)
        category = m.group(5).upper()
        description_full = m.group(6).strip()

        state = LessonState(state_str)

        # Derive confidence (backward compatible)
        if conf_str is not None:
            confidence = float(conf_str)
        elif state == LessonState.RULE:
            confidence = 0.90
        elif state == LessonState.PATTERN:
            confidence = 0.70  # default for unscored patterns
        elif state == LessonState.UNTESTABLE:
            confidence = 0.0
        else:
            confidence = INITIAL_CONFIDENCE

        # Derive fire_count (new field; 0 when reading old-format files)
        fire_count = int(fires_str) if fires_str is not None else 0

        # Extract root cause if embedded in description
        root_cause = ""
        rc_match = _ROOT_CAUSE_RE.search(description_full)
        if rc_match:
            root_cause = rc_match.group(1).strip()
            # Description is everything before "Root cause:"
            desc_end = description_full.lower().find("root cause:")
            description = description_full[:desc_end].strip().rstrip(".")
            if not description:
                description = description_full
        else:
            description = description_full

        lessons.append(Lesson(
            date=date_str,
            state=state,
            confidence=confidence,
            category=category,
            description=description,
            root_cause=root_cause,
            fire_count=fire_count,
        ))

    return lessons


# ---------------------------------------------------------------------------
# Confidence Updates
# ---------------------------------------------------------------------------

def update_confidence(
    lessons: list[Lesson],
    corrections_this_session: list[dict],
    applications_this_session: list[dict] | None = None,
    total_sessions: int = 0,
    session_categories: set[str] | None = None,
    brain_mode: str = BRAIN_MODE_OWNER,
) -> list[Lesson]:
    """Apply one session's worth of confidence updates to all lessons.

    Args:
        lessons: Current active lessons.
        corrections_this_session: List of dicts, each with at least a
            "category" key (str). These are CORRECTION events from the
            current session.
        applications_this_session: Optional list of dicts representing
            lesson applications during the session. Each dict has keys:
                - ``lesson_category`` (str): category of the applied lesson
                - ``accepted`` (bool): output was accepted / improved
                - ``misfired`` (bool): lesson was applied but output was worse
            When None, behaves exactly as before (backward compatible).
        total_sessions: Total sessions the brain has been trained on.
            Used for maturity-aware kill switches (SPEC Section 1).
            If 0, uses default UNTESTABLE_SESSION_LIMIT.
        session_categories: Set of categories that were ACTIVE this session
            (i.e., task types the user actually worked on). Lessons whose
            category is not in this set don't increment sessions_since_fire.
            If None, all categories are considered relevant (backward compat).
        brain_mode: "owner" (training, kill switches active) or
            "renter" (using, lessons frozen — no kills, no demotion).

    Returns:
        Updated list of lessons (mutated in place AND returned).

    Rules applied per lesson (owner mode, FSRS power-law model):
        - If lesson category matches a correction: confidence -= fsrs_penalty(current)
        - If corrections exist but NOT in this category: confidence += fsrs_bonus(current)
        - If session was RELEVANT but no fires: sessions_since_fire += 1
        - If session was NOT RELEVANT: sessions_since_fire unchanged
        - Accepted application: fire_count += 1, confidence += fsrs_bonus(current) * 0.5
        - Misfired application: misfire_count += 1, confidence -= fsrs_penalty(current)
        - Promote INSTINCT -> PATTERN at 0.60, REQUIRES fire_count >= 3
        - Promote PATTERN -> RULE at 0.90, REQUIRES fire_count >= 5
        - Kill switch: zero fires for N RELEVANT cycles → UNTESTABLE
          (N: INFANT=15, ADOLESCENT=12, MATURE=10, STABLE=8)
        - FSRS: bonuses are larger at low confidence (~0.12 at 0.30) and
          smaller near ceiling (~0.05 at 0.80). Penalties = 2x bonus at
          current confidence. This replaces flat linear constants.

    Renter mode:
        - Lessons are READ-ONLY. No confidence changes, no kills.
        - Renter can flag lessons via explicit RULE_APPLICATION events
          (misfired=True marks a lesson as unhelpful for their use case)
          but the lesson is not auto-deleted.
    """
    # Renter mode: lessons are frozen. Only process explicit misfired flags.
    if brain_mode == BRAIN_MODE_RENTER:
        if applications_this_session:
            for lesson in lessons:
                for app in (applications_this_session or []):
                    if (app.get("lesson_category", "").upper() == lesson.category
                            and app.get("misfired")):
                        lesson.misfire_count += 1  # Track feedback, don't change confidence
        return lessons

    correction_cats: set[str] = {
        c.get("category", "").upper()
        for c in corrections_this_session
        if c.get("category")
    }
    has_corrections = len(correction_cats) > 0

    # Build lookup: category -> list of application records
    app_map: dict[str, list[dict]] = {}
    if applications_this_session is not None:
        for app in applications_this_session:
            cat = app.get("lesson_category", "").upper()
            if cat:
                app_map.setdefault(cat, []).append(app)

    for lesson in lessons:
        # Skip untestable lessons only — RULES can still be demoted on misfire
        if lesson.state == LessonState.UNTESTABLE:
            continue

        # Determine if this session was RELEVANT to this lesson's category.
        # Only relevant sessions count toward the kill switch.
        session_relevant = (
            session_categories is None  # backward compat: all sessions relevant
            or lesson.category in session_categories
        )

        # --- Process explicit application records first ---
        if applications_this_session is not None:
            for app in app_map.get(lesson.category, []):
                if app.get("misfired"):
                    lesson.misfire_count += 1
                    penalty = fsrs_penalty(lesson.confidence)
                    lesson.confidence = round(
                        max(0.0, lesson.confidence - penalty), 2
                    )
                elif app.get("accepted"):
                    lesson.fire_count += 1
                    lesson.sessions_since_fire = 0
                    # Acceptance bonus = half the survival bonus at current level
                    bonus = fsrs_bonus(lesson.confidence) * 0.5
                    lesson.confidence = round(
                        min(1.0, lesson.confidence + bonus), 2
                    )

        # --- Session-level correction signal ---
        if lesson.category in correction_cats:
            # Lesson FAILED — same category got corrected again.
            # Do NOT increment fire_count: a contradiction is not a successful
            # application. Incrementing here would let a never-applied lesson
            # satisfy MIN_APPLICATIONS_FOR_PATTERN via contradictions alone,
            # and would reset sessions_since_fire preventing UNTESTABLE archival.
            penalty = fsrs_penalty(lesson.confidence)
            lesson.confidence = round(
                max(0.0, lesson.confidence - penalty), 2
            )

        elif has_corrections:
            # Corrections happened elsewhere — this lesson held
            bonus = fsrs_bonus(lesson.confidence)
            lesson.confidence = round(
                min(1.0, lesson.confidence + bonus), 2
            )
            # Only count relevant sessions toward kill switch
            if session_relevant:
                lesson.sessions_since_fire += 1

        else:
            # No corrections at all — only increment if session was relevant
            if session_relevant:
                lesson.sessions_since_fire += 1

        # --- Promotion logic (gated by minimum applications) ---
        if (
            lesson.state == LessonState.INSTINCT
            and lesson.confidence >= PATTERN_THRESHOLD
            and lesson.fire_count >= MIN_APPLICATIONS_FOR_PATTERN
        ):
            lesson.state = LessonState.PATTERN

        if (
            lesson.state == LessonState.PATTERN
            and lesson.confidence >= RULE_THRESHOLD
            and lesson.fire_count >= MIN_APPLICATIONS_FOR_RULE
        ):
            lesson.state = LessonState.RULE

        # --- Kill switch (maturity-aware) ---
        kill_threshold = (
            get_kill_switch_threshold(total_sessions)
            if total_sessions > 0
            else UNTESTABLE_SESSION_LIMIT
        )
        # Kill 1: Never fired at all after N relevant cycles
        if (
            lesson.sessions_since_fire >= kill_threshold
            and lesson.fire_count == 0
        ):
            lesson.state = LessonState.UNTESTABLE

        # Kill 2: Oscillating — misfires >= fires AND stale for N/2 relevant cycles.
        # A lesson that fires sometimes but misfires equally is net-zero value.
        if (
            lesson.misfire_count > 0
            and lesson.misfire_count >= lesson.fire_count
            and lesson.sessions_since_fire >= kill_threshold // 2
            and lesson.state != LessonState.UNTESTABLE
        ):
            lesson.state = LessonState.UNTESTABLE

    return lessons


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def format_lessons(lessons: list[Lesson]) -> str:
    """Serialize a list of Lessons back to markdown format.

    Output format (new, includes fire_count):
        [DATE] [STATE:CONFIDENCE:FIRES] CATEGORY: description. Root cause: ...

    RULE and UNTESTABLE also include confidence and fires for round-trip fidelity:
        [DATE] [RULE:0.90:7] CATEGORY: description
        [DATE] [UNTESTABLE:0.00:0] CATEGORY: description
    """
    lines: list[str] = []
    for lesson in lessons:
        tag = f"[{lesson.state.value}:{lesson.confidence:.2f}:{lesson.fire_count}]"

        desc = lesson.description
        if lesson.root_cause:
            # Ensure description ends with period before root cause
            if not desc.endswith("."):
                desc += "."
            desc += f" Root cause: {lesson.root_cause}"

        lines.append(f"[{lesson.date}] {tag} {lesson.category}: {desc}")

    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# Graduation
# ---------------------------------------------------------------------------

def graduate(lessons: list[Lesson]) -> tuple[list[Lesson], list[Lesson]]:
    """Split lessons into active and graduated.

    Returns:
        (active, graduated) — graduated are lessons with state == RULE.
        UNTESTABLE lessons are also moved to graduated (archived).
    """
    active: list[Lesson] = []
    graduated: list[Lesson] = []

    for lesson in lessons:
        if lesson.state in (LessonState.RULE, LessonState.UNTESTABLE):
            graduated.append(lesson)
        else:
            active.append(lesson)

    return active, graduated


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

def compute_learning_velocity(lessons: list[Lesson]) -> dict:
    """Compute metrics about the brain's learning trajectory.

    Args:
        lessons: All lessons (active + archived/graduated).

    Returns:
        Dict with:
            graduation_rate: fraction of lessons that reached RULE
            avg_time_to_pattern: average sessions_since_fire for PATTERN+ lessons
                                 (proxy — actual session count requires event log)
            avg_time_to_rule: average sessions_since_fire for RULE lessons
            correction_categories: dict of category -> count
            state_distribution: dict of state -> count
            total_lessons: int
    """
    if not lessons:
        return {
            "graduation_rate": 0.0,
            "avg_time_to_pattern": 0.0,
            "avg_time_to_rule": 0.0,
            "correction_categories": {},
            "state_distribution": {},
            "total_lessons": 0,
        }

    total = len(lessons)
    rules = [ls for ls in lessons if ls.state == LessonState.RULE]
    patterns_and_above = [
        ls for ls in lessons
        if ls.state in (LessonState.PATTERN, LessonState.RULE)
    ]

    # State distribution
    state_dist: dict[str, int] = {}
    for lesson in lessons:
        key = lesson.state.value
        state_dist[key] = state_dist.get(key, 0) + 1

    # Category distribution
    cat_dist: dict[str, int] = {}
    for lesson in lessons:
        cat_dist[lesson.category] = cat_dist.get(lesson.category, 0) + 1

    # Confidence-based time estimates
    # From INSTINCT (0.30) to PATTERN (0.60) at +0.10/session = ~3 sessions minimum
    # From INSTINCT (0.30) to RULE (0.90) at +0.10/session = ~6 sessions minimum
    # We estimate based on confidence delta from initial
    def _estimated_sessions(conf: float) -> float:
        """Estimate sessions elapsed based on confidence (FSRS-aware)."""
        if conf <= INITIAL_CONFIDENCE:
            return 0.0
        # FSRS: average bonus decreases as confidence rises.
        # Approximate by integrating the bonus curve from INITIAL to conf.
        # At 0.30->0.60: ~3-4 sessions. At 0.30->0.90: ~8-12 sessions.
        steps = 0
        c = INITIAL_CONFIDENCE
        while c < conf and steps < 100:
            c += fsrs_bonus(c)
            steps += 1
        return float(steps)

    avg_to_pattern = 0.0
    if patterns_and_above:
        avg_to_pattern = round(
            sum(_estimated_sessions(min(ls.confidence, PATTERN_THRESHOLD))
                for ls in patterns_and_above) / len(patterns_and_above),
            1,
        )

    avg_to_rule = 0.0
    if rules:
        avg_to_rule = round(
            sum(_estimated_sessions(min(ls.confidence, RULE_THRESHOLD))
                for ls in rules) / len(rules),
            1,
        )

    graduation_rate = round(len(rules) / total, 3) if total > 0 else 0.0

    return {
        "graduation_rate": graduation_rate,
        "avg_time_to_pattern": avg_to_pattern,
        "avg_time_to_rule": avg_to_rule,
        "correction_categories": cat_dist,
        "state_distribution": state_dist,
        "total_lessons": total,
    }
