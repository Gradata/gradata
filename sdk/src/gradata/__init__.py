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

from gradata.exceptions import (
    BrainError,
    BrainNotFoundError,
    EventPersistenceError,
    TaxonomyError,
    EmbeddingError,
    ExportError,
    ValidationError,
)
from gradata._paths import BrainContext  # noqa: F401
from gradata._types import Lesson, LessonState  # noqa: F401
from gradata._self_improvement import (
    compute_learning_velocity,
    format_lessons,
    graduate,
    parse_lessons,
    update_confidence,
)
from gradata.brain import Brain
from gradata.onboard import onboard

# ── Pattern exports (standalone utilities) ──────────────────────────────
from gradata.patterns.pipeline import Pipeline, Stage, GateResult, PipelineResult
from gradata.patterns.parallel import ParallelBatch, ParallelTask, DependencyGraph, merge_results
from gradata.patterns.memory import EpisodicMemory, SemanticMemory, ProceduralMemory, MemoryManager
from gradata.patterns.guardrails import InputGuard, OutputGuard, Guard, GuardCheck
from gradata.patterns.mcp import MCPBridge, MCPToolSchema, MCPServer
from gradata.patterns.human_loop import assess_risk, RiskAssessment, HumanLoopGate
from gradata.patterns.reflection import CritiqueChecklist, Criterion, reflect, EMAIL_CHECKLIST
from gradata.patterns.evaluator import EvalDimension, evaluate_optimize_loop
from gradata.patterns.scope import AudienceTier, TaskType, classify_scope
from gradata.patterns.sub_agents import Delegation, DelegationResult, orchestrate
from gradata.patterns.rag import SmartRAG, NaiveRAG
from gradata.patterns.rule_tracker import RuleApplication

__all__ = [
    # Core
    "Brain",
    "BrainContext",
    "Lesson",
    "LessonState",
    "__version__",
    "compute_learning_velocity",
    "format_lessons",
    "graduate",
    "onboard",
    "parse_lessons",
    "update_confidence",
    # Pipeline
    "Pipeline", "Stage", "GateResult", "PipelineResult",
    # Parallel
    "ParallelBatch", "ParallelTask", "DependencyGraph", "merge_results",
    # Memory
    "EpisodicMemory", "SemanticMemory", "ProceduralMemory", "MemoryManager",
    # Guardrails
    "InputGuard", "OutputGuard", "Guard", "GuardCheck",
    # MCP
    "MCPBridge", "MCPToolSchema", "MCPServer",
    # Human Loop
    "assess_risk", "RiskAssessment", "HumanLoopGate",
    # Reflection
    "CritiqueChecklist", "Criterion", "reflect", "EMAIL_CHECKLIST",
    # Evaluator
    "EvalDimension", "evaluate_optimize_loop",
    # Scope
    "AudienceTier", "TaskType", "classify_scope",
    # Sub-Agents
    "Delegation", "DelegationResult", "orchestrate",
    # RAG
    "SmartRAG", "NaiveRAG",
    # Rule Tracker
    "RuleApplication",
]
