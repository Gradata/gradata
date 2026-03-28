"""
Gradata — Personal AI brains that compound knowledge over time.

Quick start:
    from gradata import Brain
    brain = Brain.init("./my-brain")

    # Core learning loop
    brain.log_output("draft email text", output_type="email", self_score=7)
    brain.correct(draft="original", final="user-edited version")
    brain.apply_brain_rules("draft cold email to CTO")

    # Search + retrieval
    brain.search("budget objections")

    # Quality
    brain.manifest()
    brain.export()
"""

__version__ = "0.1.0"

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

from gradata._paths import BrainContext
from gradata._self_improvement import (
    compute_learning_velocity,
    format_lessons,
    graduate,
    parse_lessons,
    update_confidence,
)
from gradata._types import Lesson, LessonState, RuleTransferScope
from gradata.brain import Brain
from gradata.exceptions import (
    BrainError,
    BrainNotFoundError,
    EmbeddingError,
    EventPersistenceError,
    ExportError,
    TaxonomyError,
    ValidationError,
)
from gradata.onboard import onboard
from gradata.patterns.evaluator import EvalDimension, evaluate_optimize_loop
from gradata.patterns.guardrails import Guard, GuardCheck, InputGuard, OutputGuard
from gradata.patterns.human_loop import HumanLoopGate, RiskAssessment, assess_risk
from gradata.patterns.mcp import MCPBridge, MCPServer, MCPToolSchema
from gradata.patterns.memory import EpisodicMemory, MemoryManager, ProceduralMemory, SemanticMemory
from gradata.patterns.parallel import DependencyGraph, ParallelBatch, ParallelTask, merge_results

# ── Pattern exports (standalone utilities) ──────────────────────────────
from gradata.patterns.pipeline import GateResult, Pipeline, PipelineResult, Stage
from gradata.patterns.rag import NaiveRAG, SmartRAG
from gradata.patterns.reflection import EMAIL_CHECKLIST, Criterion, CritiqueChecklist, reflect
from gradata.patterns.rule_tracker import RuleApplication
from gradata.patterns.scope import AudienceTier, TaskType, classify_scope
from gradata.patterns.sub_agents import Delegation, DelegationResult, orchestrate

__all__ = [
    # Core API — these are the public surface
    "Brain",
    "BrainContext",
    "Lesson",
    "LessonState",
    "RuleTransferScope",
    "__version__",
    # Graduation pipeline
    "compute_learning_velocity",
    "format_lessons",
    "graduate",
    "onboard",
    "parse_lessons",
    "update_confidence",
    # Patterns available via: from gradata.patterns import Pipeline, SmartRAG, etc.
    # Import lines above are kept for backward compat (from gradata import Pipeline still works)
    # but patterns are NOT in __all__ — use gradata.patterns for * imports.
]
