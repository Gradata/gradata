"""
Layer 0: Base Agentic Patterns.

patterns/ never imports from enhancements/.
Pure logic, no external dependencies.

Usage:
    from gradata.patterns import Pipeline, Stage
    from gradata.patterns import SmartRAG, NaiveRAG
    from gradata.patterns import InputGuard, OutputGuard
"""

from gradata.patterns.evaluator import EvalDimension, evaluate_optimize_loop
from gradata.patterns.guardrails import Guard, GuardCheck, InputGuard, OutputGuard
from gradata.patterns.human_loop import HumanLoopGate, RiskAssessment, assess_risk
from gradata.patterns.mcp import MCPBridge, MCPServer, MCPToolSchema
from gradata.patterns.memory import EpisodicMemory, MemoryManager, ProceduralMemory, SemanticMemory
from gradata.patterns.parallel import DependencyGraph, ParallelBatch, ParallelTask, merge_results
from gradata.patterns.pipeline import GateResult, Pipeline, PipelineResult, Stage
from gradata.patterns.rag import NaiveRAG, SmartRAG
from gradata.patterns.reflection import EMAIL_CHECKLIST, Criterion, CritiqueChecklist, reflect
from gradata.patterns.rule_tracker import RuleApplication
from gradata.patterns.scope import AudienceTier, TaskType, classify_scope
from gradata.patterns.sub_agents import Delegation, DelegationResult, orchestrate

__all__ = [
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
