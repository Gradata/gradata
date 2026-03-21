# Outcome Schema — [Profession] Pack

## Outcome Types

Define the types of tactic→result pairs you want to track:

| Type | Description | Storage Location |
|------|------------|------------------|
| example-type-1 | [What this outcome represents] | [Where to store it] |
| example-type-2 | [What this outcome represents] | [Where to store it] |

## Outcome Entry Format

```
## [DATE] [TYPE] — [TARGET/CONTEXT]
- **Tactic:** [what was done]
- **Result:** [what happened]
- **Tags:** [relevant tags for pattern matching]
- **Signal:** [positive|negative|neutral]
```

## Pattern Detection

After logging, scan recent entries of the same type:
- 3+ similar tactics with same result direction → flag as emerging pattern
- Format: `Pattern emerging: [tactic type] → [result] (N/M times)`
