# Meta-Rule Generalization: Before & After

Meta-rules emerge when 3+ graduated RULE lessons share a common theme. The system synthesizes them into a higher-order behavioral principle.

## How It Works

```
Individual corrections → Lessons (INSTINCT) → Graduated rules (RULE) → Meta-rule
```

A meta-rule is NOT a summary. It's a *generalization* that captures the principle behind multiple specific rules. This means the brain can apply the principle to new situations it hasn't seen before.

## Real Example: Process Discipline

**Before (3 separate RULE lessons):**

```
[RULE:0.92] PROCESS: Never jump to implementation. Always: Plan → Adversary → Fix → THEN build
[RULE:0.88] PROCESS: Always audit existing code before proposing new files — prevents duplication
[RULE:0.85] PROCESS: When the user asks "what's next", refresh Gmail/calendar first, don't assume
```

**After (meta-rule emerges):**

```
META-RULE [process_discipline] (confidence: 0.88, sources: 3):
  "Verify before acting. Check existing state (code, email, calendar) before
   creating new artifacts or making assumptions. Plan before building."
```

The meta-rule captures what the three rules share: *don't act on stale assumptions*. Now when the system encounters a NEW situation (e.g., "create a PR"), it can apply the principle: "verify the branch state before creating."

## Real Example: Communication Tone

**Before (4 separate RULE lessons):**

```
[RULE:0.91] DRAFTING: Never use em dashes in email prose. Use colons, commas, or rewrite.
[RULE:0.87] DRAFTING: No bold mid-paragraph in emails. Bold only for headers/names.
[RULE:0.84] TONE: Don't ask "want me to continue?" — just keep building until told to stop.
[RULE:0.82] COMMUNICATION: Always hyperlink scheduling link URL, never paste raw URLs.
```

**After (meta-rule emerges):**

```
META-RULE [communication_tone] (confidence: 0.86, sources: 4):
  "Match the user's communication style: direct prose (no em dashes, no mid-paragraph bold),
   actionable (no permission-seeking), professional formatting (hyperlinks not raw URLs)."
```

## What Makes This Different From a Linter

A linter catches: `em dash detected → flag`
A meta-rule captures: `The user prefers direct, unformatted prose` → applies to ALL future writing, including situations the original rules never covered.

The meta-rule would prevent a new correction like "don't use semicolons as sentence connectors" because it already knows the user prefers simple punctuation — even though no specific semicolon rule exists.

## Verification

Run the meta-rule discovery on your own brain:

```python
from gradata import Brain
brain = Brain("./my-brain")

# Check if enough rules exist for meta-rules
rules = brain.export_rules_json(min_state="RULE")
print(f"RULE lessons: {len(rules)}")

# Meta-rules need 3+ RULE lessons in the same category
from collections import Counter
cats = Counter(r["category"] for r in rules)
for cat, count in cats.most_common():
    if count >= 3:
        print(f"  {cat}: {count} rules → meta-rule eligible")
```

Meta-rules typically emerge after 30-50 sessions with regular corrections.
