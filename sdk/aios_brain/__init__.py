"""
AIOS Brain SDK — Personal AI brains that compound knowledge over time.

Quick start:
    from aios_brain import Brain
    brain = Brain.init("./my-brain")
    brain.search("budget objections")
    brain.embed()
    brain.manifest()
"""

__version__ = "0.1.0"

from aios_brain.brain import Brain
from aios_brain.onboard import onboard
from aios_brain._self_improvement import (
    LessonState,
    Lesson,
    parse_lessons,
    update_confidence,
    format_lessons,
    graduate,
    compute_learning_velocity,
)

__all__ = [
    "Brain",
    "onboard",
    "LessonState",
    "Lesson",
    "parse_lessons",
    "update_confidence",
    "format_lessons",
    "graduate",
    "compute_learning_velocity",
    "__version__",
]
