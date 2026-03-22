# Self-Improvement Pipeline (v2.0)

Three steps. No meta-layers. Evidence-driven.

## The Pipeline

```
INSTINCT (confidence 0.00 - 0.59)
    |  +0.10 per session where it prevents a mistake
    |  -0.15 per session where Oliver corrects despite the rule
    v
PATTERN (confidence 0.60 - 0.89)
    |  Accumulates evidence via [TRACK:N/3]
    |  3+ fires across 2+ sessions -> promote
    v
RULE (confidence 0.90+)
    |  Permanent in CARL / CLAUDE.md / gates
    |  Kill switch: 10 cycles zero value (INFANT phase)
    v
ARCHIVE (graduated, reference only)
```

## Confidence Scoring

| Status | Confidence | Format in lessons.md |
|--------|-----------|---------------------|
| New lesson (just created) | 0.30 | `[INSTINCT:0.30]` |
| Surviving probation | 0.30-0.59 | `[INSTINCT:0.45]` |
| Ready to promote | 0.60 | Auto-promotes to `[PATTERN]` |
| Confirmed pattern | 0.60-0.89 | `[PATTERN]` with `[CONFIRM:N/3]` |
| Graduated to rule | 0.90+ | Moves to permanent file |

## How Confidence Updates (at wrap-up)

1. Query `events` table for this session's CORRECTION events
2. For each active instinct/pattern:
   - If a scenario occurred where the lesson applies AND it prevented the mistake: +0.10
   - If a scenario occurred where the lesson applies AND Oliver corrected anyway: -0.15
   - If no scenario occurred: no change (don't penalize rarity)
3. Any instinct reaching 0.60+ auto-promotes to PATTERN
4. Any instinct dropping below 0.00: kill it (the rule was wrong)

## Shadow Mode (optional for uncertain rules)

Tag `[SHADOW:0/3]`. Track what WOULD have been different. After 3 occurrences:
- 2+ positive -> promote to INSTINCT
- 2+ negative -> kill
- Mixed -> extend 3 more

## Kill Switches (by maturity phase)

| Phase | Sessions | Zero-Value Threshold | Action |
|-------|----------|---------------------|--------|
| INFANT | 0-50 | 10 cycles | Flag only |
| ADOLESCENT | 50-100 | 7 cycles | Auto-flag, Oliver confirms |
| MATURE | 100-200 | 5 cycles | Auto-delete, Oliver notified |
| STABLE | 200+ | 3 cycles | Aggressive pruning |

## What Replaced What

| Old (v1) | New (v2) | Why |
|----------|----------|-----|
| L1 Loop (tag-track-learn) | Instinct->Pattern->Rule | Same concept, unified naming |
| L2 System Loop (system-patterns.md) | events.jsonl queries | Data in DB, not markdown |
| L3 Cross-Wiring (21 wires) | Hooks + event queries | Enforced, not aspirational |
| L4 Meta-Loop (never ran) | Killed | Premature abstraction |
| L5 Convergence (never ran) | Killed | Premature abstraction |
| [PROVISIONAL:N] format | [INSTINCT:0.30] format | Confidence > countdown |
| Neural bus markdown | events.jsonl + SQLite | Queryable, hook-driven |
