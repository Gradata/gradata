"""Layer 0: base agentic patterns. Pure logic, no external deps; never
imports from enhancements/. Lazy-loads submodules (Pipeline/Stage,
SmartRAG/NaiveRAG, InputGuard/OutputGuard) on first access.
"""

# Lazy-load all pattern modules — nothing imported at module load time.
# This keeps `import gradata` fast; individual patterns load on first access.

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    # Loop detection
    "LoopAction": (".loop_detection", "LoopAction"),
    "LoopDetector": (".loop_detection", "LoopDetector"),
    "LoopDetectorConfig": (".loop_detection", "LoopDetectorConfig"),
    # Middleware chain
    "Middleware": (".middleware", "Middleware"),
    "MiddlewareChain": (".middleware", "MiddlewareChain"),
    "MiddlewareContext": (".middleware", "MiddlewareContext"),
    "MiddlewareError": (".middleware", "MiddlewareError"),
    # Context brackets
    "ContextBracket": (".context_brackets", "ContextBracket"),
    "ContextTracker": (".context_brackets", "ContextTracker"),
    "get_bracket": (".context_brackets", "get_bracket"),
    "get_bracket_guidance": (".context_brackets", "get_bracket_guidance"),
    "is_action_allowed": (".context_brackets", "is_action_allowed"),
    # Evaluator
    "EvalDimension": (".evaluator", "EvalDimension"),
    "evaluate_optimize_loop": (".evaluator", "evaluate_optimize_loop"),
    # Execute/Qualify
    "ExecuteQualifyLoop": (".execute_qualify", "ExecuteQualifyLoop"),
    "ExecuteQualifyResult": (".execute_qualify", "ExecuteQualifyResult"),
    "FailureClassification": (".execute_qualify", "FailureClassification"),
    "QualifyResult": (".execute_qualify", "QualifyResult"),
    "QualifyScore": (".execute_qualify", "QualifyScore"),
    # Guardrails
    "Guard": (".guardrails", "Guard"),
    "GuardCheck": (".guardrails", "GuardCheck"),
    "InputGuard": (".guardrails", "InputGuard"),
    "OutputGuard": (".guardrails", "OutputGuard"),
    # Human loop
    "HumanLoopGate": (".human_loop", "HumanLoopGate"),
    "RiskAssessment": (".human_loop", "RiskAssessment"),
    "assess_risk": (".human_loop", "assess_risk"),
    # MCP
    "MCPBridge": (".mcp", "MCPBridge"),
    "MCPServer": (".mcp", "MCPServer"),
    "MCPToolSchema": (".mcp", "MCPToolSchema"),
    # Memory
    "EpisodicMemory": (".memory", "EpisodicMemory"),
    "MemoryManager": (".memory", "MemoryManager"),
    "ProceduralMemory": (".memory", "ProceduralMemory"),
    "SemanticMemory": (".memory", "SemanticMemory"),
    # Parallel
    "DependencyGraph": (".parallel", "DependencyGraph"),
    "ParallelBatch": (".parallel", "ParallelBatch"),
    "ParallelTask": (".parallel", "ParallelTask"),
    "merge_results": (".parallel", "merge_results"),
    # Pipeline
    "GateResult": (".pipeline", "GateResult"),
    "Pipeline": (".pipeline", "Pipeline"),
    "PipelineResult": (".pipeline", "PipelineResult"),
    "Stage": (".pipeline", "Stage"),
    # Q-Learning router
    "QLearningRouter": (".q_learning_router", "QLearningRouter"),
    "RouteDecision": (".q_learning_router", "RouteDecision"),
    "RouterConfig": (".q_learning_router", "RouterConfig"),
    # RAG
    "NaiveRAG": (".rag", "NaiveRAG"),
    "SmartRAG": (".rag", "SmartRAG"),
    # Reconciliation
    "ActualResult": (".reconciliation", "ActualResult"),
    "DeviationScore": (".reconciliation", "DeviationScore"),
    "PlanItem": (".reconciliation", "PlanItem"),
    "Reconciler": (".reconciliation", "Reconciler"),
    "ReconciliationSummary": (".reconciliation", "ReconciliationSummary"),
    # Reflection
    "EMAIL_CHECKLIST": (".reflection", "EMAIL_CHECKLIST"),
    "Criterion": (".reflection", "Criterion"),
    "CritiqueChecklist": (".reflection", "CritiqueChecklist"),
    "reflect": (".reflection", "reflect"),
    # Sub-agents
    "Delegation": (".sub_agents", "Delegation"),
    "DelegationResult": (".sub_agents", "DelegationResult"),
    "orchestrate": (".sub_agents", "orchestrate"),
    # Task escalation (moved to execute_qualify)
    "TaskOutcome": (".execute_qualify", "TaskOutcome"),
    "TaskStatus": (".execute_qualify", "TaskStatus"),
    "is_actionable": (".execute_qualify", "is_actionable"),
    "report_outcome": (".execute_qualify", "report_outcome"),
    "requires_human": (".execute_qualify", "requires_human"),
}

__all__ = list(_LAZY_IMPORTS.keys())


def __getattr__(name: str):
    if name in _LAZY_IMPORTS:
        import importlib

        rel_module, attr = _LAZY_IMPORTS[name]
        mod = importlib.import_module(rel_module, __package__)
        return getattr(mod, attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
