"""Context-budget-aware rule injection compression."""

from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gradata._types import Lesson


class ContextBudget(IntEnum):
    EMERGENCY = 1  # Single highest-confidence rule, bare text
    MINIMAL = 2  # Top 2 rules, description only
    COMPACT = 3  # RULE-state only, max 3, compressed format
    STANDARD = 4  # max_rules rules, full XML, no examples
    FULL = 5  # All rules, full formatting, examples included


def filter_by_budget(lessons: list[Lesson], budget: int = 5, max_rules: int = 5) -> list[Lesson]:
    """Filter and limit lessons based on context budget level."""
    from gradata._types import ELIGIBLE_STATES, LessonState

    if budget <= 3:  # EMERGENCY / MINIMAL / COMPACT
        eligible = [l for l in lessons if l.state == LessonState.RULE]
        eligible.sort(key=lambda l: -l.confidence)
        return eligible[:budget]
    else:  # STANDARD / FULL
        eligible = [l for l in lessons if l.state in ELIGIBLE_STATES]
        eligible.sort(key=lambda l: -l.confidence)
        return eligible[:max_rules]


def format_by_budget(lesson: Lesson, budget: int = 5) -> str:
    """Format a single rule's injection text based on budget."""
    if budget <= 1:
        return lesson.description
    elif budget <= 2:
        return f"{lesson.category}: {lesson.description}"
    elif budget <= 3:
        return f"<rule>{lesson.category}: {lesson.description}</rule>"
    else:
        return f'<rule confidence="{lesson.confidence:.2f}">{lesson.category}: {lesson.description}</rule>'
