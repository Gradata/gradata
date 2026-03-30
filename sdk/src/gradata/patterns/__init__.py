"""
Layer 0: Base Agentic Patterns.

patterns/ never imports from enhancements/.
Pure logic, no external dependencies.

Usage:
    from gradata.patterns import Pipeline, Stage
    from gradata.patterns import SmartRAG, NaiveRAG
    from gradata.patterns import InputGuard, OutputGuard
"""

from gradata.patterns.loop_detection import LoopAction, LoopDetector, LoopDetectorConfig
from gradata.patterns.middleware import Middleware, MiddlewareChain, MiddlewareContext, MiddlewareError
from gradata.patterns.context_brackets import (
    ContextBracket,
    ContextTracker,
    get_bracket,
    get_bracket_guidance,
    is_action_allowed,
)
from gradata.patterns.evaluator import EvalDimension, evaluate_optimize_loop
from gradata.patterns.execute_qualify import (
    ExecuteQualifyLoop,
    ExecuteQualifyResult,
    FailureClassification,
    QualifyResult,
    QualifyScore,
)
from gradata.patterns.guardrails import Guard, GuardCheck, InputGuard, OutputGuard
from gradata.patterns.human_loop import HumanLoopGate, RiskAssessment, assess_risk
from gradata.patterns.mcp import MCPBridge, MCPServer, MCPToolSchema
from gradata.patterns.memory import EpisodicMemory, MemoryManager, ProceduralMemory, SemanticMemory
from gradata.patterns.parallel import DependencyGraph, ParallelBatch, ParallelTask, merge_results
from gradata.patterns.pipeline import GateResult, Pipeline, PipelineResult, Stage
from gradata.patterns.q_learning_router import QLearningRouter, RouteDecision, RouterConfig
from gradata.patterns.rag import NaiveRAG, SmartRAG
from gradata.patterns.reconciliation import (
    ActualResult,
    DeviationScore,
    PlanItem,
    Reconciler,
    ReconciliationSummary,
)
from gradata.patterns.reflection import EMAIL_CHECKLIST, Criterion, CritiqueChecklist, reflect
from gradata.patterns.rule_tracker import RuleApplication
from gradata.patterns.scope import AudienceTier, TaskType, classify_scope
from gradata.patterns.sub_agents import Delegation, DelegationResult, orchestrate
from gradata.patterns.task_escalation import (
    TaskOutcome,
    TaskStatus,
    is_actionable,
    report_outcome,
    requires_human,
)

__all__ = [
    # Loop detection (adapted from deer-flow)
    "LoopAction",
    "LoopDetector",
    "LoopDetectorConfig",
    # Middleware chain (adapted from deer-flow)
    "Middleware",
    "MiddlewareChain",
    "MiddlewareContext",
    "MiddlewareError",
    # Context brackets (adapted from paul)
    "ContextBracket",
    "ContextTracker",
    "get_bracket",
    "get_bracket_guidance",
    "is_action_allowed",
    # Execute/Qualify loop (adapted from paul)
    "ExecuteQualifyLoop",
    "ExecuteQualifyResult",
    "FailureClassification",
    "QualifyResult",
    "QualifyScore",
    # Q-Learning router (adapted from ruflo)
    "QLearningRouter",
    "RouteDecision",
    "RouterConfig",
    # Reconciliation / UNIFY (adapted from paul)
    "ActualResult",
    "DeviationScore",
    "PlanItem",
    "Reconciler",
    "ReconciliationSummary",
    # Task escalation (adapted from paul)
    "TaskOutcome",
    "TaskStatus",
    "is_actionable",
    "report_outcome",
    "requires_human",
    # Existing exports
    "EMAIL_CHECKLIST",
    "AudienceTier",
    "Criterion",
    "CritiqueChecklist",
    "Delegation",
    "DelegationResult",
    "DependencyGraph",
    "EpisodicMemory",
    "EvalDimension",
    "GateResult",
    "Guard",
    "GuardCheck",
    "HumanLoopGate",
    "InputGuard",
    "MCPBridge",
    "MCPServer",
    "MCPToolSchema",
    "MemoryManager",
    "NaiveRAG",
    "OutputGuard",
    "ParallelBatch",
    "ParallelTask",
    "Pipeline",
    "PipelineResult",
    "ProceduralMemory",
    "RiskAssessment",
    "RuleApplication",
    "SemanticMemory",
    "SmartRAG",
    "Stage",
    "TaskType",
    "assess_risk",
    "classify_scope",
    "evaluate_optimize_loop",
    "merge_results",
    "orchestrate",
    "reflect",
]
