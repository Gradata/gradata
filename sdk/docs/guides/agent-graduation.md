# Agent Graduation Guide

This guide explains how to set up and use agent graduation to promote reliable agents to higher autonomy.

## When to Use Agent Graduation

Use it when your system delegates to sub-agents (research, drafting, analysis, etc.) and you want to:

- Track which agents produce good output
- Automatically increase autonomy for reliable agents
- Catch and demote agents that regress
- Propagate lessons across agents (upward distillation)

## Setup

Agent graduation initializes automatically when you create a Brain:

```python
from aios_brain import Brain

brain = Brain("./my-brain")
tracker = brain.agent_graduation
```

## Logging Agent Output

Every time an agent produces output, record the outcome:

```python
# Agent produced good output (approved without edits)
tracker.record_outcome(
    "research",
    output_preview="Summary of findings...",
    outcome="approved",
    edits=None,
    session=42,
)

# Agent produced output that needed correction
tracker.record_outcome(
    "research",
    output_preview="Summary of findings...",
    outcome="edited",
    edits="rewrote the conclusion section",
    session=42,
)
```

## Checking Agent Gate

Before running an agent, check its current approval gate to decide how much oversight to apply:

```python
gate = tracker.get_approval_gate("research")  # lowercase: "confirm" | "preview" | "auto"

if gate == "confirm":
    # Show output to human, wait for approval
    result = agent.run(task)
    approved = human_review(result)
elif gate == "preview":
    # Show output but don't block
    result = agent.run(task)
    show_preview(result)
elif gate == "auto":
    # Run without review
    result = agent.run(task)
    use_directly(result)
```

## Promotion Thresholds

| Transition | Confidence Required |
|------------|-------------------|
| CONFIRM → PREVIEW | 0.60+ |
| PREVIEW → AUTO | 0.90+ |
| Any → demotion | Drops below tier threshold |

Confidence scoring:

- **+0.10** per session with accepted output
- **-0.15** per correction or rejection

## Upward Distillation

When sub-agents accumulate proven lessons (PATTERN confidence or above), those lessons can be distilled up to the brain level:

```python
# Distill all agent lessons at PATTERN+ confidence to brain level
distilled = tracker.distill_upward()  # min_state=PATTERN by default

for lesson in distilled:
    print(f"Agent: {lesson['agent_type']}, Lesson: {lesson['text']}")
```

The distillation scans all agents automatically. Only lessons that have reached PATTERN confidence are promoted.

## Best Practices

1. **Start all agents at CONFIRM**. Let them earn trust.
2. **Log every review**, not just corrections. Accepted outputs increase confidence.
3. **Use meaningful agent IDs** that map to specific capabilities.
4. **Review demotion alerts**. A sudden demotion signals regression.
5. **Check agent tiers at session start** to catch overnight changes.
