# Patterns API Reference

Layer 0 patterns are accessible both through the `Brain` class and directly via imports.

## Orchestrator

```python
from aios_brain.patterns.orchestrator import classify_request

result = classify_request("draft a cold email to the VP of Marketing")
# result.intent = "draft"
# result.selected_pattern = "pipeline"
# result.audience = "executive"
```

## Pipeline

```python
from aios_brain.patterns.pipeline import Pipeline, Stage

def research(ctx):
    ctx["data"] = fetch_data()
    return ctx

def draft(ctx):
    ctx["output"] = generate_draft(ctx["data"])
    return ctx

pipeline = Pipeline(
    Stage("research", research),
    Stage("draft", draft),
)
result = pipeline.run({"query": "budget objections"})
```

## Parallel

```python
from aios_brain.patterns.parallel import DependencyGraph, ParallelTask

graph = DependencyGraph([
    ParallelTask("task_a", "Run task A", fn_a),
    ParallelTask("task_b", "Run task B", fn_b),
    ParallelTask("task_c", "Run task C", fn_c, depends_on=["task_a", "task_b"]),
])
results = graph.run()  # task_a and task_b run in the same wave
```

## Reflection

```python
from aios_brain.patterns.reflection import reflect, EMAIL_CHECKLIST, default_evaluator

result = reflect(
    output="Draft email text...",
    checklist=EMAIL_CHECKLIST,
    evaluator=default_evaluator,
    refiner=my_refiner_fn,
    max_cycles=3,
)
# result.final_output, result.converged, result.cycles_used
```

## Evaluator

```python
from aios_brain.patterns.evaluator import Evaluator

evaluator = Evaluator(scorer=my_scorer, threshold=8.0, max_iterations=3)
result = evaluator.run(initial_draft)
```

## Memory

```python
from aios_brain.patterns.memory import MemoryManager

mm = MemoryManager()
mm.store("semantic", "Prefers bullet points in emails")
mm.store("episodic", "Met with VP yesterday, discussed budget")
results = mm.retrieve("email preferences", types=["semantic"])
print(results[0].content)
```

## Guardrails

```python
from aios_brain.patterns.guardrails import (
    InputGuard, OutputGuard,
    pii_detector, injection_detector,
    banned_phrases, destructive_action,
)

input_guard = InputGuard(pii_detector, injection_detector)
checks = input_guard.check("User input text")

output_guard = OutputGuard(banned_phrases, destructive_action)
checks = output_guard.check("AI output text")
```

## Human Loop

```python
from aios_brain.patterns.human_loop import assess_risk

result = assess_risk("delete all prospect files", {"domain": "sales"})
# result.tier = "high"
# result.reversible = False
```

## Scope

```python
from aios_brain.patterns.scope import classify_scope, register_task_type

scope = classify_scope({"task": "draft cold email", "audience": "CTO"})
# scope.task_type = "email_draft"
# scope.audience_tier = "executive"

# Register custom task types
register_task_type("proposal", ["proposal", "rfp", "bid"], "sales")
```

## Rule Engine

```python
from aios_brain.patterns.rule_engine import apply_rules, format_rules_for_prompt

matched = apply_rules(lessons, scope)
prompt_text = format_rules_for_prompt(matched)
```

## Rule Tracker

```python
from aios_brain.patterns.rule_tracker import log_application

log_application(
    rule_id="TONE_001",
    session=42,
    accepted=True,
    misfired=False,
)
```

## Tools

```python
from aios_brain.patterns.tools import ToolRegistry, ToolSpec

registry = ToolRegistry()
registry.register(
    ToolSpec(name="search", description="Search the brain", parameters={...}),
    handler=search_handler,
)
```

## MCP

```python
from aios_brain.patterns.mcp import MCPBridge

bridge = MCPBridge("my-brain")  # string name, not Brain instance
result = bridge.handle_call("brain_search", {"query": "email tone"})
```
