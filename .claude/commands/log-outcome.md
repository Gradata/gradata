---
description: Log a tactic-to-result outcome for pattern tracking
allowed-tools: Read, Edit, Write, Bash, Grep, AskUserQuestion
---

## Arguments
- First argument: freeform description of what was done and what happened
- `--type`: Override auto-detected type (email|call|demo|proposal|objection|close|linkedin|lead-filter)

## Context
- Patterns file: @brain/emails/PATTERNS.md (if exists)
- Prospect vault: brain/prospects/

## Your Task

Log the outcome of a sales tactic so patterns can compound over time.

### Step 1: Parse the Input

Extract from the user's description:
- **Tactic**: What was done (email angle, call approach, demo structure, objection response)
- **Target**: Who it was aimed at (prospect name, company, segment)
- **Result**: What happened (reply, no reply, booked, objection, close, ghost)
- **Type**: Auto-detect from context or use --type override

### Step 2: Format the Outcome Entry

```
## [DATE] [TYPE] — [TARGET]
- **Tactic:** [what was done]
- **Result:** [what happened]
- **Tags:** [angle], [framework], [segment]
- **Signal:** [positive|negative|neutral]
```

### Step 3: Route the Entry

Based on type:

| Type | Destination | Action |
|------|-------------|--------|
| email | brain/emails/PATTERNS.md | Add to outcomes table, update win/loss counts |
| call | brain/prospects/[name].md | Add to call history section |
| demo | brain/prospects/[name].md | Add to demo notes section |
| proposal | brain/prospects/[name].md | Add to deal progression |
| objection | brain/emails/PATTERNS.md | Add to objection patterns |
| close | brain/pipeline/ | Log win/loss with debrief |
| linkedin | brain/emails/PATTERNS.md | Add to LinkedIn outcomes |
| lead-filter | brain/emails/PATTERNS.md | Add to filtering outcomes |

### Step 4: Check for Pattern Emergence

After logging, scan the last 10 entries of the same type:
- 3+ similar tactics with same result direction → flag as emerging pattern
- Show: `Pattern emerging: [tactic type] → [result] (N/M times)`

### Step 5: Confirm

```
Logged: [TYPE] outcome for [TARGET]
  Tactic: [summary]
  Result: [summary]
  Pattern check: [emerging pattern or "no new patterns"]
```
