---
description: End-of-session close routine — summary, outcomes, handoff
allowed-tools: Read, Edit, Write, Bash, Grep, Glob, AskUserQuestion
---

## Context
- Learnings queue: !`python .claude/hooks/reflect/scripts/read_queue.py 2>/dev/null || echo "[]"`

## What hooks handle automatically (DO NOT duplicate)
These fire when the session ends — no manual steps needed:
- Correction capture → `auto_correct.py` (PostToolUse hook)
- Memory → lessons sync → `memory-bridge.py` (SessionStart hook)
- Graduation sweep → `graduation-sweep.py` (Stop hook)
- Meta-rule discovery → `session-close-data.js` (Stop hook)
- FTS rebuild + manifest + brain git commit → `brain-maintain.js` (Stop hook)
- Session corrections from notes → `capture-session-corrections.py` (Stop hook)

## Your Task (what hooks CAN'T do)

### Step 1: Process Queued Learnings

```bash
python .claude/hooks/reflect/scripts/read_queue.py 2>/dev/null || echo "[]"
```

If queue has items: classify, dedupe, route (behavioral → CLAUDE.md, specific → lessons.md).
If empty: skip.

### Step 2: Write Session Summary

Create `brain/sessions/YYYY-MM-DD-SNN.md`:

```markdown
---
date: YYYY-MM-DD
session: NN
type: sales|system
focus: [one line]
---

# Session Summary

## What Was Done
- [bullet list]

## Outcomes
- [deals, emails, leads, code changes]

## Corrections This Session
- [list corrections — hooks will parse these into lessons]

## Next Session Tasks
- [what to pick up next]
```

### Step 3: Update Loop State

Rewrite `brain/loop-state.md` with Oliver's summary + next session tasks.
This is what the next session reads at startup.

### Step 4: Verify Hooks Ran

Quick check that the automated pipeline is healthy:

```bash
python -c "
import sys; sys.path.insert(0, 'sdk/src')
from gradata.brain import Brain
from gradata.patterns.rule_context import get_rule_context
brain = Brain('C:/Users/olive/SpritesWork/brain')
ctx = get_rule_context()
stats = ctx.stats()
print(f'RuleContext: {stats[\"total_rules\"]} rules | {stats[\"rule_tier\"]} RULE | {stats[\"pattern_tier\"]} PATTERN')
result = brain.end_session()
print(f'Graduation: {result[\"promotions\"]} promoted, {result[\"demotions\"]} demoted, {result.get(\"total_lessons\", 0)} total')
"
```

If this errors, something in the pipeline is broken — investigate before closing.

### Step 5: Done

```
SESSION CLOSE
  Summary:    brain/sessions/[date]-S[N].md
  Loop state: brain/loop-state.md
  Pipeline:   [healthy/error]
```
