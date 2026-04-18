"""
Gradata — Procedural memory for AI agents.

Quick start:
    from . import Brain
    brain = Brain.init("./my-brain")

    # Core correction loop (builds procedural memory)
    brain.log_output("draft email text", output_type="email", self_score=7)
    brain.correct(draft="original", final="user-edited version")
    brain.apply_brain_rules("draft message to stakeholder")

    # Search + retrieval
    brain.search("budget objections")

    # Quality
    brain.manifest()
    brain.export()
"""

try:
    from importlib.metadata import PackageNotFoundError as _PkgNotFound
    from importlib.metadata import version as _pkg_version
    try:
        __version__ = _pkg_version("gradata")
    except _PkgNotFound:
        # Editable install without installed metadata
        __version__ = "0.0.0+editable"
except ImportError:
    __version__ = "0.0.0+unknown"

# ── Debug logging via env var (like OPENAI_LOG=debug) ──────────────────
import logging as _logging
import os as _os

_log_level = _os.environ.get("GRADATA_LOG", "").upper()
if _log_level in ("DEBUG", "INFO", "WARNING", "ERROR"):
    _logging.basicConfig(
        level=getattr(_logging, _log_level),
        format="%(name)s %(levelname)s: %(message)s",
    )
    _logging.getLogger("gradata").setLevel(getattr(_logging, _log_level))

from ._paths import BrainContext
from ._scoped_brain import ScopedBrain
from ._types import Lesson, LessonState, RuleTransferScope
from .brain import Brain
from .context_wrapper import brain_context
from .enhancements.self_improvement import (
    compute_learning_velocity,
    format_lessons,
    graduate,
    parse_lessons,
    update_confidence,
)
from .exceptions import (
    BrainError,
    BrainNotFoundError,
    EmbeddingError,
    EventPersistenceError,
    ExportError,
    TaxonomyError,
    ValidationError,
)
from .notifications import Notification
from .onboard import onboard

__all__ = [
    # Core API
    "Brain",
    "BrainContext",
    "BrainError",
    "BrainNotFoundError",
    "EmbeddingError",
    "EventPersistenceError",
    "ExportError",
    "Lesson",
    "LessonState",
    "Notification",
    "RuleTransferScope",
    "ScopedBrain",
    "TaxonomyError",
    "ValidationError",
    "__version__",
    "brain_context",
    "compute_learning_velocity",
    "format_lessons",
    "graduate",
    "onboard",
    "parse_lessons",
    "update_confidence",
]
