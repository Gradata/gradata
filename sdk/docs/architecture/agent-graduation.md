# Agent Graduation

Agent Graduation applies the same INSTINCT-PATTERN-RULE pipeline to agent and sub-agent outputs, promoting reliable agents to higher autonomy levels.

## The Problem

When an AI system delegates to sub-agents, how do you know which agents to trust? Agent Graduation tracks each agent's correction history and promotes or demotes them based on performance.

## Approval Tiers

```
CONFIRM → PREVIEW → AUTO
```

| Tier | Behavior | When |
|------|----------|------|
| **CONFIRM** | Human reviews every output | New agents, high-risk tasks |
| **PREVIEW** | Human sees output, can skip review | Agents with moderate track record |
| **AUTO** | Output used without review | Agents with proven reliability |

## How It Works

1. **Agent produces output** -- logged as an event with the agent's ID.
2. **Human reviews** -- accepts, edits, or rejects the output.
3. **Correction tracked** -- if edited, the correction is recorded against the agent's profile.
4. **Confidence updated** -- same +0.10/-0.15 scoring as lesson graduation.
5. **Tier promotion** -- when confidence crosses threshold, agent moves to next tier.

## Upward Distillation

Lessons learned by sub-agents bubble up to the orchestrator. If a research agent learns that a particular data source is unreliable, that lesson propagates to the orchestrator's rule set.

This prevents the same mistake from being learned independently by multiple agents.

## Configuration

```python
brain = Brain("./my-brain")

# Agent graduation is initialized automatically
tracker = brain.agent_graduation

# Check an agent's current tier
tier = tracker.get_tier("research-agent")

# Log an agent output review
tracker.log_review(
    agent_id="research-agent",
    accepted=True,
    session=42,
)
```

## Research Basis

The graduation thresholds are informed by:

- **Brown et al. (2024)**: Calibration of human-AI trust in automation
- **NIST Bayesian Framework**: Statistical confidence in system reliability
- **Lee & See (2004)**: Trust in automation, appropriate reliance
