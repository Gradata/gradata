# Layer 0: Patterns

Layer 0 contains 15 reusable agentic patterns. These are the building blocks for any AI agent system. They have zero external dependencies and never import from Layer 1.

## Pattern Catalog

### Orchestrator

Routes user requests to the appropriate pattern based on intent classification. Analyzes the message, determines task type, audience tier, and selects the best pattern to handle it.

```python
from gradata.contrib.patterns.orchestrator import classify_request

result = classify_request("draft a follow-up email to the CFO")
# ClassificationResult(intent='draft', pattern='pipeline', audience='executive')
```

### Pipeline

Sequential stages with quality gates. Each stage transforms input and must pass a gate before the next stage runs.

```python
from gradata.contrib.patterns.pipeline import Pipeline, Stage

pipeline = Pipeline(
    Stage("research", research_fn, gate=quality_check),
    Stage("draft", draft_fn, gate=tone_check),
    Stage("review", review_fn),
)
result = pipeline.run(initial_input)
```

### Parallel

Dependency graph execution with wave processing. Tasks with no unmet dependencies run concurrently.

```python
from gradata.contrib.patterns.parallel import DependencyGraph, ParallelTask

graph = DependencyGraph([
    ParallelTask("enrich", "Enrich prospect data", enrich_fn),
    ParallelTask("research", "Research company", research_fn),
    ParallelTask("draft", "Draft email", draft_fn, depends_on=["enrich", "research"]),
])
results = graph.run()
```

### Reflection

Generate-critique-refine loop. Produces output, evaluates it against a checklist, and refines until convergence or max cycles.

```python
result = brain.reflect(
    draft="Hi John, wanted to touch base...",
    max_cycles=3,
)
print(result["converged"])     # True/False
print(result["cycles_used"])   # 1-3
```

### Evaluator

Score-gated optimization. Runs a scoring function and iterates until the score meets a threshold.

```python
from gradata.contrib.patterns.evaluator import Evaluator

evaluator = Evaluator(
    scorer=score_fn,
    threshold=8.0,
    max_iterations=3,
)
result = evaluator.run(draft)
```

### Memory

Three memory types for different retention needs:

| Type | Lifespan | Use Case |
|------|----------|----------|
| **Episodic** | Session-scoped | What happened in this conversation |
| **Semantic** | Persistent | Facts, knowledge, learned patterns |
| **Procedural** | Persistent | How-to knowledge, workflows, rules |

```python
from gradata.contrib.patterns.memory import MemoryManager

mm = MemoryManager()
mm.store("semantic", "User prefers bullet points")
results = mm.retrieve("formatting preferences")
```

### Guardrails

Input and output safety checks. Detects PII, prompt injection, banned phrases, and destructive actions.

```python
result = brain.guard("Delete all user data", direction="input")
# {"blocked": True, "block_reason": "destructive_action: ..."}

result = brain.guard("Here's the analysis...", direction="output")
# {"all_passed": True, "blocked": False}
```

### Human Loop

Risk-tiered approval gates. Classifies actions by risk and requires human approval for high-risk operations.

```python
result = brain.assess_risk("send email to 500 contacts")
# {"tier": "high", "reason": "bulk operation", "reversible": False}
```

### Sub-Agents

Structured delegation with contracts. Defines what a sub-agent can do, what it must return, and how to validate its output.

### RAG

FTS5 keyword search with graduation-aware scoring. Search results are boosted by the confidence level of their source (RULE > PATTERN > INSTINCT).

### Rule Engine

Scope-aware rule selection and prompt injection. Matches rules to the current task context and formats them for LLM consumption.

### Rule Tracker

Logs rule application events (accepted, misfired, contradicted) for graduation scoring.

### Scope

Task type and audience tier classification. Domain-agnostic: detects intent from keywords, not hardcoded categories.

### Tools

Tool registry with plan-before-execute. Tools declare their capabilities; the orchestrator plans which tools to use before executing.

### MCP

Brain-to-host protocol bridge. Exposes brain operations as MCP tools for Claude Code, Cursor, and other MCP hosts.
