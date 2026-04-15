"""
Gradata — Procedural memory for AI agents.

Quick start:
    from gradata import Brain
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

__version__ = "0.5.0"

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
from gradata._scoped_brain import ScopedBrain
from gradata._types import Lesson, LessonState, RuleTransferScope
from gradata.brain import Brain
from gradata.context_wrapper import brain_context
from gradata.enhancements.self_improvement import (
    compute_learning_velocity,
    format_lessons,
    graduate,
    parse_lessons,
    update_confidence,
)
from gradata.exceptions import (
    BrainError,
    BrainNotFoundError,
    EmbeddingError,
    EventPersistenceError,
    ExportError,
    TaxonomyError,
    ValidationError,
)
from gradata.notifications import Notification
from gradata.onboard import onboard

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

# ── Lazy pattern loading ──────────────────────────────────────────────
# Patterns are NOT loaded at import time. Access via:
#   from gradata.patterns import Pipeline, SmartRAG, Guard, etc.
# Backward compat: `from gradata import Pipeline` still works via __getattr__.

_PATTERN_IMPORTS: dict[str, tuple[str, str]] = {
    # name -> (module, attribute)
    # contrib.patterns (moved from patterns/ in S87)
    "EvalDimension": ("gradata.contrib.patterns.evaluator", "EvalDimension"),
    "evaluate_optimize_loop": ("gradata.contrib.patterns.evaluator", "evaluate_optimize_loop"),
    "Guard": ("gradata.contrib.patterns.guardrails", "Guard"),
    "GuardCheck": ("gradata.contrib.patterns.guardrails", "GuardCheck"),
    "InputGuard": ("gradata.contrib.patterns.guardrails", "InputGuard"),
    "OutputGuard": ("gradata.contrib.patterns.guardrails", "OutputGuard"),
    "HumanLoopGate": ("gradata.contrib.patterns.human_loop", "HumanLoopGate"),
    "RiskAssessment": ("gradata.contrib.patterns.human_loop", "RiskAssessment"),
    "assess_risk": ("gradata.contrib.patterns.human_loop", "assess_risk"),
    "MCPBridge": ("gradata.contrib.patterns.mcp", "MCPBridge"),
    "MCPServer": ("gradata.contrib.patterns.mcp", "MCPServer"),
    "MCPToolSchema": ("gradata.contrib.patterns.mcp", "MCPToolSchema"),
    "EpisodicMemory": ("gradata.contrib.patterns.memory", "EpisodicMemory"),
    "MemoryManager": ("gradata.contrib.patterns.memory", "MemoryManager"),
    "ProceduralMemory": ("gradata.contrib.patterns.memory", "ProceduralMemory"),
    "SemanticMemory": ("gradata.contrib.patterns.memory", "SemanticMemory"),
    "DependencyGraph": ("gradata.contrib.patterns.parallel", "DependencyGraph"),
    "ParallelBatch": ("gradata.contrib.patterns.parallel", "ParallelBatch"),
    "ParallelTask": ("gradata.contrib.patterns.parallel", "ParallelTask"),
    "merge_results": ("gradata.contrib.patterns.parallel", "merge_results"),
    "GateResult": ("gradata.contrib.patterns.pipeline", "GateResult"),
    "Pipeline": ("gradata.contrib.patterns.pipeline", "Pipeline"),
    "PipelineResult": ("gradata.contrib.patterns.pipeline", "PipelineResult"),
    "Stage": ("gradata.contrib.patterns.pipeline", "Stage"),
    "NaiveRAG": ("gradata.contrib.patterns.rag", "NaiveRAG"),
    "SmartRAG": ("gradata.contrib.patterns.rag", "SmartRAG"),
    "EMAIL_CHECKLIST": ("gradata.contrib.patterns.reflection", "EMAIL_CHECKLIST"),
    "Criterion": ("gradata.contrib.patterns.reflection", "Criterion"),
    "CritiqueChecklist": ("gradata.contrib.patterns.reflection", "CritiqueChecklist"),
    "reflect": ("gradata.contrib.patterns.reflection", "reflect"),
    # rules (extracted from patterns/ in S87)
    "RuleApplication": ("gradata.rules.rule_tracker", "RuleApplication"),
    "AudienceTier": ("gradata.rules.scope", "AudienceTier"),
    "TaskType": ("gradata.rules.scope", "TaskType"),
    "classify_scope": ("gradata.rules.scope", "classify_scope"),
    # contrib.patterns (sub_agents)
    "Delegation": ("gradata.contrib.patterns.sub_agents", "Delegation"),
    "DelegationResult": ("gradata.contrib.patterns.sub_agents", "DelegationResult"),
    "orchestrate": ("gradata.contrib.patterns.sub_agents", "orchestrate"),
}


def __getattr__(name: str):
    """Lazy-load patterns on first access. Backward compatible."""
    if name in _PATTERN_IMPORTS:
        import importlib
        import warnings
        module_path, attr = _PATTERN_IMPORTS[name]
        warnings.warn(
            f"Importing {name} from 'gradata' is deprecated. "
            f"Use 'from {module_path} import {attr}' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        mod = importlib.import_module(module_path)
        return getattr(mod, attr)
    raise AttributeError(f"module 'gradata' has no attribute {name!r}")
