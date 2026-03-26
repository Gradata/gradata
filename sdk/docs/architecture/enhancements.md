# Layer 1: Enhancements

Layer 1 modules wire into Layer 0 patterns to make brains compound over time. They import from `patterns/` but never the reverse.

## Enhancement Catalog

### Self-Improvement

The core graduation pipeline. Parses lessons from corrections and promotes them through confidence tiers:

```
INSTINCT (0.0-0.59) → PATTERN (0.60-0.89) → RULE (0.90+)
```

- **+0.10** confidence per surviving session
- **-0.15** per contradiction/misfire
- **UNTESTABLE** archival after 20+ sessions with 0 fires

### Agent Graduation

Applies the same graduation pipeline to agent and sub-agent outputs. Agents that consistently produce good work get promoted to higher autonomy levels:

```
CONFIRM → PREVIEW → AUTO
```

- **CONFIRM**: Human reviews every output before use.
- **PREVIEW**: Human sees output but can skip review.
- **AUTO**: Output is used without human review.

Includes upward distillation: lessons learned by sub-agents bubble up to the orchestrator.

### Diff Engine

Computes edit distance between draft and final versions. Classifies severity on a 5-level scale:

| Severity | Edit Distance | Meaning |
|----------|--------------|---------|
| as-is | 0.0 | No changes |
| minor | 0.01-0.20 | Small tweaks |
| moderate | 0.21-0.50 | Significant edits |
| major | 0.51-0.80 | Substantial rewrite |
| discarded | 0.81-1.0 | Complete replacement |

### Edit Classifier

Classifies edits into 5 categories:

- **Tone**: Voice, formality, warmth adjustments
- **Content**: Adding or removing information
- **Structure**: Reordering, reformatting, layout changes
- **Factual**: Correcting errors, wrong data, inaccuracies
- **Style**: Word choice, phrasing preferences

### Pattern Extractor

Extracts behavioral patterns from classified edits. Groups similar corrections across sessions to identify recurring preferences.

### Metrics

Rolling-window quality metrics computed from events:

- Correction rate (corrections / outputs)
- Severity distribution
- Category breakdown
- Session-over-session trends

### Failure Detectors

Four automated regression alerts:

1. **Correction spike**: Sudden increase in correction density
2. **Category regression**: One category getting worse
3. **Rule misfire surge**: Rules firing incorrectly
4. **Quality decay**: Declining output acceptance rate

### CARL (Contracts for Agent Reinforcement Learning)

Behavioral contracts per domain. Define rules, constraints, and quality standards that apply to specific work contexts.

```python
brain.register_contract(sales_contract)
constraints = brain.get_constraints("draft cold email")
```

### Quality Gates

8.0 threshold with fix cycling. Outputs scoring below 8.0 enter a fix loop:

1. Score the output
2. If below 8.0, identify gaps and fix
3. Re-score
4. Repeat until 8.0+ or escalate after 2 cycles

### Truth Protocol

Evidence-based output validation. No success claims without evidence. Every state-changing action must show tool output (IDs, paths, API responses).

### Correction Tracking

Tracks correction density, half-life, and reliability metrics:

- **MTBF** (Mean Time Between Failures): Sessions between corrections
- **MTTR** (Mean Time To Repair): How quickly corrections are addressed
- **Half-life**: How long a lesson's confidence lasts without reinforcement

### Brain Scores

Compound health metric aggregating events, corrections, graduation status, and coverage into a single report card.

### Judgment Decay

Confidence decay for idle lessons. Lessons that go unused lose confidence over time. Active lessons get reinforced. Prevents stale rules from persisting indefinitely.

### Rules Distillation

Cross-lesson pattern detection. When multiple lessons point to the same behavioral preference, proposes a consolidated rule with evidence scoring.

### Loop Intelligence

Activity tracking and pattern aggregation. Analyzes prep-to-outcome ratios (did that demo prep lead to a booked meeting?) to identify which preparation patterns actually work.

### Reports

Generates health reports, CSV exports, metrics summaries, and rule audit documents.

### Success Conditions

Six-condition validation from the Build Directive. Checks whether the brain meets its target quality metrics.

### Tone Profile

Domain-specific tone and voice tracking. Learns the preferred writing style for different contexts.
