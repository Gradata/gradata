"""
Self-Improvement Pipeline — INSTINCT -> PATTERN -> RULE
=========================================================
SDK LAYER: Pure logic, no file I/O. Caller reads/writes files,
this module transforms structured lesson data.

The pipeline:
  1. User corrects the brain -> CORRECTION event with category tag
  2. Correction becomes a LESSON at confidence 0.30 (INSTINCT)
  3. Each session survived without contradiction: confidence += 0.10
  4. At 0.60: promotes to PATTERN
  5. At 0.90: graduates to RULE (permanent behavioral change)
  6. Contradicted: confidence -= 0.15
  7. 0 fires after 20 sessions: flagged UNTESTABLE
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enums & Data Classes
# ---------------------------------------------------------------------------

class LessonState(Enum):
    """Maturity tiers for a learned lesson."""
    INSTINCT = "INSTINCT"       # 0.00 - 0.59
    PATTERN = "PATTERN"         # 0.60 - 0.89
    RULE = "RULE"               # 0.90+
    UNTESTABLE = "UNTESTABLE"   # 20+ sessions with 0 fires


@dataclass
class Lesson:
    """A single learned lesson with confidence tracking."""
    date: str                          # ISO date when the lesson was created
    state: LessonState                 # Current maturity tier
    confidence: float                  # 0.00 - 1.00
    category: str                      # e.g. DRAFTING, ACCURACY, PROCESS
    description: str                   # Full text after "CATEGORY: "
    root_cause: str = ""               # Root cause analysis (after "Root cause:")
    fire_count: int = 0                # Times the lesson was triggered/relevant
    sessions_since_fire: int = 0       # Sessions since last application

    def __post_init__(self) -> None:
        self.confidence = round(max(0.0, min(1.0, self.confidence)), 2)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INITIAL_CONFIDENCE = 0.30
SURVIVAL_BONUS = 0.10
CONTRADICTION_PENALTY = 0.15
PATTERN_THRESHOLD = 0.60
RULE_THRESHOLD = 0.90
UNTESTABLE_SESSION_LIMIT = 20


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

# Matches: [2026-03-20] [PATTERN:0.80] CATEGORY: description text
_LESSON_RE = re.compile(
    r"^\[(\d{4}-\d{2}-\d{2})\]\s+"
    r"\[(INSTINCT|PATTERN|RULE|UNTESTABLE)(?::(\d+\.\d+))?\]\s+"
    r"(\w+):\s*(.+)",
    re.DOTALL,
)

_ROOT_CAUSE_RE = re.compile(r"Root cause:\s*(.+)", re.IGNORECASE)


def parse_lessons(text: str) -> list[Lesson]:
    """Parse a lessons.md file into structured Lesson objects.

    Handles the canonical format:
        [DATE] [STATE:CONFIDENCE] CATEGORY: description. Root cause: ...

    Lines that don't match the lesson format (headers, comments, blanks)
    are silently skipped.
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
        category = m.group(4).upper()
        description_full = m.group(5).strip()

        state = LessonState(state_str)

        # Derive confidence
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
        ))

    return lessons


# ---------------------------------------------------------------------------
# Confidence Updates
# ---------------------------------------------------------------------------

def update_confidence(
    lessons: list[Lesson],
    corrections_this_session: list[dict],
) -> list[Lesson]:
    """Apply one session's worth of confidence updates to all lessons.

    Args:
        lessons: Current active lessons.
        corrections_this_session: List of dicts, each with at least a
            "category" key (str). These are CORRECTION events from the
            current session.

    Returns:
        Updated list of lessons (mutated in place AND returned).

    Rules applied per lesson:
        - If lesson category matches a correction: confidence -= 0.15
          (lesson failed to prevent the mistake).
        - If corrections exist but NOT in this category: confidence += 0.10
          (lesson survived a session with activity).
        - If no corrections at all: increment sessions_since_fire only
          (can't evaluate — no evidence).
        - Promote INSTINCT -> PATTERN at 0.60.
        - Graduate PATTERN -> RULE at 0.90.
        - Flag UNTESTABLE after 20 sessions with 0 fires.
    """
    correction_cats: set[str] = {
        c.get("category", "").upper()
        for c in corrections_this_session
        if c.get("category")
    }
    has_corrections = len(correction_cats) > 0

    for lesson in lessons:
        # Skip already-graduated or untestable lessons
        if lesson.state in (LessonState.RULE, LessonState.UNTESTABLE):
            continue

        if lesson.category in correction_cats:
            # Lesson FAILED — same category got corrected again
            lesson.confidence = round(max(0.0, lesson.confidence - CONTRADICTION_PENALTY), 2)
            lesson.fire_count += 1
            lesson.sessions_since_fire = 0

        elif has_corrections:
            # Corrections happened elsewhere — this lesson held
            lesson.confidence = round(min(1.0, lesson.confidence + SURVIVAL_BONUS), 2)
            lesson.sessions_since_fire += 1

        else:
            # No corrections at all — can't evaluate
            lesson.sessions_since_fire += 1

        # --- Promotion logic ---
        if lesson.state == LessonState.INSTINCT and lesson.confidence >= PATTERN_THRESHOLD:
            lesson.state = LessonState.PATTERN

        if lesson.state == LessonState.PATTERN and lesson.confidence >= RULE_THRESHOLD:
            lesson.state = LessonState.RULE

        # --- Untestable flag ---
        if (
            lesson.sessions_since_fire >= UNTESTABLE_SESSION_LIMIT
            and lesson.fire_count == 0
        ):
            lesson.state = LessonState.UNTESTABLE

    return lessons


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def format_lessons(lessons: list[Lesson]) -> str:
    """Serialize a list of Lessons back to markdown format.

    Output matches the canonical lessons.md format:
        [DATE] [STATE:CONFIDENCE] CATEGORY: description. Root cause: ...
    """
    lines: list[str] = []
    for lesson in lessons:
        if lesson.state == LessonState.RULE:
            tag = "[RULE]"
        elif lesson.state == LessonState.UNTESTABLE:
            tag = "[UNTESTABLE]"
        else:
            tag = f"[{lesson.state.value}:{lesson.confidence:.2f}]"

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
    rules = [l for l in lessons if l.state == LessonState.RULE]
    patterns_and_above = [
        l for l in lessons
        if l.state in (LessonState.PATTERN, LessonState.RULE)
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
        """Estimate sessions elapsed based on confidence."""
        if conf <= INITIAL_CONFIDENCE:
            return 0.0
        return (conf - INITIAL_CONFIDENCE) / SURVIVAL_BONUS

    avg_to_pattern = 0.0
    if patterns_and_above:
        avg_to_pattern = round(
            sum(_estimated_sessions(min(l.confidence, PATTERN_THRESHOLD))
                for l in patterns_and_above) / len(patterns_and_above),
            1,
        )

    avg_to_rule = 0.0
    if rules:
        avg_to_rule = round(
            sum(_estimated_sessions(min(l.confidence, RULE_THRESHOLD))
                for l in rules) / len(rules),
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
