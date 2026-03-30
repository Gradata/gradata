"""
Self-Improvement — INSTINCT → PATTERN → RULE graduation pipeline.
=================================================================
SDK LAYER: Layer 1 (enhancements). Imports from Layer 0 (patterns)
and shared types only.

This is the open-source graduation engine. It provides the full
pipeline for confidence scoring, lesson parsing, graduation, and
formatting. Constants are aligned to SPEC.md Sections 1, 6, and 13.

The proprietary cloud version (gradata_cloud.graduation.self_improvement)
adds FSRS-based scheduling and multi-brain optimization on top.
"""

from __future__ import annotations

import logging
import re

from gradata._types import (
    Lesson,
    LessonState,
    transition,
)

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (SPEC-aligned, research-backed)
# ---------------------------------------------------------------------------

INITIAL_CONFIDENCE = 0.40
PATTERN_THRESHOLD = 0.60
RULE_THRESHOLD = 0.90
MIN_APPLICATIONS_FOR_PATTERN = 3
MIN_APPLICATIONS_FOR_RULE = 5

# SPEC Section 1+6: misfire > contradiction (misfires are worse — rule was irrelevant)
MISFIRE_PENALTY = -0.25
CONTRADICTION_PENALTY = -0.24

# SPEC Section 13: EMA +0.10. v2.3: acceptance bonus kept at 0.10
ACCEPTANCE_BONUS = 0.12
# v2.3: survival is flat (no severity scaling)
SURVIVAL_BONUS = 0.08

# SPEC Section 1: maturity-aware kill switches (relevant cycles only)
KILL_LIMITS: dict[str, int] = {
    "INFANT": 15,       # 0-50 sessions
    "ADOLESCENT": 12,   # 50-100 sessions
    "MATURE": 10,       # 100-200 sessions
    "STABLE": 8,        # 200+ sessions
}
UNTESTABLE_SESSION_LIMIT = 15  # Default (INFANT)

# Severity multipliers for contradiction penalty
# Typo fix barely dents confidence; rewrite hits hard
SEVERITY_WEIGHTS: dict[str, float] = {
    "trivial": 0.15,     # typo fix: -0.20 * 0.15 = -0.03
    "minor": 0.40,       # word swap: -0.20 * 0.40 = -0.08
    "moderate": 0.70,    # sentence rewrite: -0.20 * 0.70 = -0.14
    "major": 1.00,       # significant change: -0.20 * 1.00 = -0.20
    "rewrite": 1.30,     # complete rewrite: -0.20 * 1.30 = -0.26
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

# Map diff_engine severity labels to graduation severity labels
_SEVERITY_MAP: dict[str, str] = {
    "as-is": "trivial",
    "discarded": "rewrite",
}

# Session-type → categories that are testable in that session type
# DRAFTING is immune during system sessions; ARCHITECTURE is immune during sales
CATEGORY_SESSION_MAP: dict[str, frozenset[str]] = {
    "full": frozenset(),     # empty = all categories testable
    "systems": frozenset({
        "ARCHITECTURE", "PROCESS", "TOOL", "THOROUGHNESS", "CONTEXT",
    }),
    "sales": frozenset({
        "DRAFTING", "LEADS", "PRICING", "DEMO_PREP", "POSITIONING",
        "COMMUNICATION", "TONE", "ACCURACY", "DATA_INTEGRITY",
    }),
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
        j = i + 1
        while j < len(lines) and lines[j].startswith("  "):
            meta_line = lines[j].strip()
            if meta_line.startswith("Root cause:") and not root_cause:
                root_cause = meta_line[len("Root cause:"):].strip()
            elif meta_line.startswith("Agent:"):
                agent_type = meta_line[len("Agent:"):].strip()
            meta_m = _META_RE.search(meta_line)
            if meta_m:
                fire_count = int(meta_m.group(1))
                sessions_since_fire = int(meta_m.group(2))
                misfire_count = int(meta_m.group(3))
            j += 1

        lessons.append(Lesson(
            date=date_str,
            state=state,
            confidence=confidence,
            category=category.upper(),
            description=description.rstrip(),
            root_cause=root_cause,
            fire_count=fire_count,
            sessions_since_fire=sessions_since_fire,
            misfire_count=misfire_count,
            agent_type=agent_type,
        ))
        i = j if j > i + 1 else i + 1

    return lessons


# ---------------------------------------------------------------------------
# FSRS-Inspired Confidence Functions
# ---------------------------------------------------------------------------
# Spaced repetition insight: bonuses shrink as confidence rises (diminishing
# returns), penalties shrink as confidence drops (floor protection).
# This prevents runaway confidence and makes the 0.90 RULE threshold genuinely
# hard to reach — requires sustained, repeated success.


def fsrs_bonus(confidence: float) -> float:
    """Confidence-dependent survival bonus (FSRS-inspired).

    Higher confidence → smaller bonus (diminishing returns).
    At confidence 0.30: ~0.08. At 0.80: ~0.06. At 0.95: ~0.05.
    """
    return round(ACCEPTANCE_BONUS * (1.0 - confidence * 0.5), 4)


def fsrs_penalty(confidence: float) -> float:
    """Confidence-dependent contradiction penalty (FSRS-inspired).

    Higher confidence → larger penalty (more to lose).
    At confidence 0.30: ~0.14. At 0.80: ~0.18. At 0.95: ~0.20.
    """
    return round(abs(CONTRADICTION_PENALTY) * (0.5 + confidence * 0.5), 4)


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
    """
    if renter:
        return lessons

    corrections = corrections_this_session or []
    severity_data = severity_data or {}

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
        if cat and "severity_label" in c and cat not in (severity_data or {}):
            inline_severity[cat] = c["severity_label"]

    # Merge inline severity into severity_data
    if inline_severity:
        severity_data = {**(severity_data or {}), **inline_severity}

    kill_limit = KILL_LIMITS.get(maturity, KILL_LIMITS["INFANT"])

    for lesson in lessons:
        # Skip terminal states
        if lesson.state in (LessonState.KILLED, LessonState.ARCHIVED):
            continue

        cat = lesson.category.upper()

        # Session-type immunity: skip lessons whose category isn't testable
        if not _is_testable(cat, session_type):
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
                # Contradiction: FSRS-based confidence-dependent penalty
                base_penalty = fsrs_penalty(lesson.confidence)
                if severity_data and cat in severity_data:
                    # Severity-weighted: scale by severity label
                    raw_severity = severity_data[cat]
                    severity = _normalize_severity(raw_severity)
                    weight = SEVERITY_WEIGHTS.get(severity, SEVERITY_WEIGHTS["moderate"])
                    penalty = base_penalty * weight
                else:
                    # No severity data: apply full FSRS penalty (backward compat)
                    penalty = base_penalty
                lesson.confidence = round(
                    max(0.0, min(1.0, lesson.confidence - penalty)), 2
                )
            else:
                # Survived: category was testable, corrections exist elsewhere
                base_bonus = fsrs_bonus(lesson.confidence)
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
                lesson.confidence = round(
                    max(0.0, min(1.0, lesson.confidence + bonus)), 2
                )

        # Track sessions since fire
        lesson.sessions_since_fire += 1

        # Inline UNTESTABLE detection
        if (
            lesson.fire_count == 0
            and lesson.sessions_since_fire >= kill_limit
            and lesson.state not in (
                LessonState.UNTESTABLE, LessonState.KILLED, LessonState.ARCHIVED
            )
        ):
            lesson.state = LessonState.UNTESTABLE

    # Inline promotion/demotion after confidence updates
    # (UNTESTABLE detection already handled above — don't re-run
    # full graduate() which would kill newly-flagged UNTESTABLE lessons)
    for lesson in lessons:
        if lesson.state in (LessonState.KILLED, LessonState.ARCHIVED, LessonState.UNTESTABLE):
            continue
        # Promote PATTERN -> RULE
        if (
            lesson.state == LessonState.PATTERN
            and lesson.confidence >= RULE_THRESHOLD
            and lesson.fire_count >= MIN_APPLICATIONS_FOR_RULE
        ) or (
            lesson.state == LessonState.INSTINCT
            and lesson.confidence >= PATTERN_THRESHOLD
            and lesson.fire_count >= MIN_APPLICATIONS_FOR_PATTERN
        ):
            lesson.state = transition(lesson.state, "promote")
        # Demote PATTERN -> INSTINCT
        elif (
            lesson.state == LessonState.PATTERN
            and lesson.confidence < PATTERN_THRESHOLD
        ):
            lesson.state = transition(lesson.state, "demote")

    return lessons


# ---------------------------------------------------------------------------
# Graduation
# ---------------------------------------------------------------------------


def graduate(
    lessons: list[Lesson],
    *,
    maturity: str = "INFANT",
    renter: bool = False,
) -> tuple[list[Lesson], list[Lesson]]:
    """Apply state transitions and split into active vs graduated.

    Mutates lessons in-place. Returns (active, graduated) where:
      - active = INSTINCT + PATTERN (still learning)
      - graduated = RULE + UNTESTABLE + KILLED + ARCHIVED (terminal or proven)

    SPEC guardrail: no promotion from silence. fire_count must meet
    minimum thresholds even if confidence is high enough.

    Args:
        lessons: Lessons to evaluate for promotion/demotion/kill.
        maturity: Brain maturity phase for kill-switch thresholds.
        renter: If True, skip all mutations (renter mode: lessons frozen).
    """
    if renter:
        active = [l for l in lessons if l.state in (LessonState.INSTINCT, LessonState.PATTERN)]
        graduated = [l for l in lessons if l.state not in (LessonState.INSTINCT, LessonState.PATTERN)]
        return active, graduated

    kill_limit = KILL_LIMITS.get(maturity, KILL_LIMITS["INFANT"])

    for lesson in lessons:
        if lesson.state in (LessonState.KILLED, LessonState.ARCHIVED, LessonState.UNTESTABLE):
            continue

        # Kill: confidence at zero (UNTESTABLE excluded — it has its own lifecycle)
        if lesson.confidence <= 0.0:
            try:
                lesson.state = transition(lesson.state, "kill")
            except ValueError:
                pass
            continue

        # Kill: untestable (too many sessions without a fire)
        if lesson.sessions_since_fire >= kill_limit:
            if lesson.state == LessonState.UNTESTABLE:
                try:
                    lesson.state = transition(lesson.state, "kill")
                except ValueError:
                    pass
                continue
            elif lesson.state in (LessonState.INSTINCT, LessonState.PATTERN):
                lesson.state = LessonState.UNTESTABLE
                continue

        # Promote PATTERN -> RULE
        if (
            lesson.state == LessonState.PATTERN
            and lesson.confidence >= RULE_THRESHOLD
            and lesson.fire_count >= MIN_APPLICATIONS_FOR_RULE
        ):
            lesson.state = transition(lesson.state, "promote")
            continue

        # Promote INSTINCT -> PATTERN
        if (
            lesson.state == LessonState.INSTINCT
            and lesson.confidence >= PATTERN_THRESHOLD
            and lesson.fire_count >= MIN_APPLICATIONS_FOR_PATTERN
        ):
            lesson.state = transition(lesson.state, "promote")
            continue

        # Demote PATTERN -> INSTINCT
        if (
            lesson.state == LessonState.PATTERN
            and lesson.confidence < PATTERN_THRESHOLD
        ):
            lesson.state = transition(lesson.state, "demote")
            continue

    # Split into active vs graduated
    active = [l for l in lessons if l.state in (LessonState.INSTINCT, LessonState.PATTERN)]
    graduated = [l for l in lessons if l.state not in (LessonState.INSTINCT, LessonState.PATTERN)]
    return active, graduated


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

        lines.append("")  # blank line between lessons

    return "\n".join(lines).rstrip() + "\n" if lines else ""


# ---------------------------------------------------------------------------
# Learning Velocity
# ---------------------------------------------------------------------------


def compute_learning_velocity(
    lessons: list[Lesson],
    window: int = 10,
) -> dict:
    """Measure how fast the brain is learning.

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
        if rule_lessons else 0.0
    )

    return {
        "graduation_rate": round(rules / total, 3) if total else 0.0,
        "total_lessons": total,
        "state_distribution": state_dist,
        "correction_categories": cat_dist,
        "avg_time_to_rule": round(avg_time, 1),
    }
