---
description: Reflect on session corrections and route learnings to the right target (with human review)
allowed-tools: Read, Edit, Write, Glob, Bash, Grep, AskUserQuestion, TodoWrite
---

## Arguments
- `--dry-run`: Preview all changes without prompting or writing.
- `--scan-history`: Scan ALL past sessions for corrections (useful for first-time setup or cold start).
- `--days N`: Limit history scan to last N days (default: 30). Only used with `--scan-history`.
- `--targets`: Show detected config files and exit.
- `--review`: Show learnings with stale/decayed entries for review.
- `--dedupe`: Scan CLAUDE.md and lessons.md for similar entries and propose consolidations.
- `--model MODEL`: Model for semantic analysis (default: `sonnet`).

## Context
- Project CLAUDE.md: @CLAUDE.md
- Lessons file: @.claude/lessons.md
- Learnings queue: !`python .claude/hooks/reflect/scripts/read_queue.py 2>/dev/null || echo "[]"`
- Current project: !`pwd`

## Routing Logic (CRITICAL — this is what makes it work)

Every learning MUST be classified into exactly one of three routes:

### Route 1: Behavioral Rule → CLAUDE.md
**What goes here:** Universal behavioral directives that should govern ALL future sessions.
- "Always do X before Y"
- "Never do X without checking Y"
- "When [situation], always [action]"
- Process changes, workflow rules, voice/tone rules
- Guardrails about scope, permissions, tools

**Where in CLAUDE.md:** Append to the most relevant existing section. If no section fits, append to `## Work Style Rules`.

**Format:** Single bullet point, imperative voice. Include a `_Why:` italic suffix if the reason isn't obvious.

### Route 2: Specific Mistake → .claude/lessons.md
**What goes here:** Corrections tied to a specific incident with a root cause.
- "You used the wrong API / tool / data source"
- "You drafted an email with banned words"
- "You forgot to check Pipedrive before asking me"
- Anything with a pattern: "What happened → What to do instead"

**Format:** Follow the existing lessons.md format:
```
[DATE] [PROVISIONAL:5] CATEGORY: What happened → What to do instead
```

**Categories:** Match existing categories in lessons.md (DRAFTING, LANGUAGE, CTA, FORMAT, TONE, RESEARCH, CRM, PROCESS, STRATEGY, ACCURACY, TOOL, ICP, SIGNATURE).

### Route 3: Methodology Insight → Flag for Manual Review
**What goes here:** Strategic observations that need Oliver's judgment before becoming rules.
- "This approach works better for [type of prospect]"
- "The market seems to be shifting toward X"
- "This objection handling pattern is effective"
- Insights about sales methodology, ICP refinement, competitive intelligence

**Action:** Present to user with recommendation. Do NOT auto-write. Ask:
```
This looks like a methodology insight, not a rule or mistake fix.
Suggested: [the insight]
Route options:
  1. Add to brain/emails/PATTERNS.md (if it's an outreach pattern)
  2. Add to brain/prospects/ vault (if prospect-specific)
  3. Add to CLAUDE.md as a rule (if you're sure it's universal)
  4. Skip for now
```

## Your Task

### Step 0: Initialize Task Tracking

Use TodoWrite immediately to show progress. Adjust based on arguments passed.

### Step 1: Parse Arguments

Check for flags: `--dry-run`, `--scan-history`, `--days N`, `--targets`, `--review`, `--dedupe`, `--model`.

If `--targets`: discover and display all target files (CLAUDE.md, .claude/lessons.md, brain/ vault), then exit.

### Step 2: Load Learnings Queue

```bash
python .claude/hooks/reflect/scripts/read_queue.py 2>/dev/null || echo "[]"
```

If queue is empty and `--scan-history` not passed:
```
No learnings queued. Corrections are auto-detected during sessions.
Use "remember: <learning>" to explicitly queue items.
Run /reflect --scan-history to scan past sessions.
```

### Step 3: Scan History (if --scan-history)

Find session files:
```bash
# Get project session directory
PROJECT_DIR="C--Users-olive-OneDrive-Desktop-Sprites-Work"
SESSION_PATH="$HOME/.claude/projects/$PROJECT_DIR/"
find "$SESSION_PATH" -name "*.jsonl" -mtime -30 -type f 2>/dev/null | head -20
```

Extract corrections using the reflect scripts:
```bash
python .claude/hooks/reflect/scripts/extract_session_learnings.py <session-file> --corrections-only
python .claude/hooks/reflect/scripts/extract_tool_rejections.py <session-file>
```

### Step 4: Classify Each Learning

For each queued item, determine the route:

1. **Read the learning text**
2. **Check if it's a behavioral rule** (universal, applies across sessions, imperative voice)
3. **Check if it's a specific mistake** (has a root cause, tied to an incident, pattern of "did X → should have done Y")
4. **Check if it's a methodology insight** (strategic, needs judgment, about market/prospect/approach)

Present classification to user:
```
════════════════════════════════════════════════════════════
REFLECT: [N] learnings to process
════════════════════════════════════════════════════════════

1. [0.85] "don't send emails without checking Pipedrive first"
   Route: CLAUDE.md (behavioral rule)
   Target section: ## Work Style Rules

2. [0.70] "used wrong threadId for Hassan's follow-up"
   Route: .claude/lessons.md (specific mistake)
   Category: CRM

3. [0.75] "gap selling angle worked better than CCQ for PE rollups"
   Route: MANUAL REVIEW (methodology insight)
   Suggestion: brain/emails/PATTERNS.md

════════════════════════════════════════════════════════════
Apply all? [y/n/edit]
```

### Step 5: Check for Duplicates

Before writing:
- Search CLAUDE.md for semantically similar rules
- Search .claude/lessons.md for similar lessons (including graduated index)
- If duplicate found, show it and ask: "Similar entry exists. Skip or update?"

### Step 6: Apply Changes

For each approved learning:

**Route 1 (CLAUDE.md):** Use Edit tool to append bullet point to the target section.

**Route 2 (lessons.md):** Use Edit tool to append new lesson entry with today's date, `[PROVISIONAL:5]` tag, and correct category.

**Route 3 (Manual):** Present recommendation and wait for user decision.

### Step 7: Clear Queue

After all learnings are processed:
```bash
python -c "
import sys, os
sys.path.insert(0, os.path.join('.claude', 'hooks', 'reflect', 'scripts'))
from lib.reflect_utils import save_queue
save_queue([])
"
```

### Step 8: Check for Rule Upgrades

After processing, scan .claude/lessons.md for 3+ similar corrections in the same category. If found:
```
Found 3+ similar corrections in [CATEGORY]:
- [lesson 1]
- [lesson 2]
- [lesson 3]

These could be consolidated into a CLAUDE.md rule.
Proposed rule: "[synthesized rule]"
Add to CLAUDE.md? [y/n]
```

### Step 9: Summary

```
════════════════════════════════════════════════════════════
REFLECT COMPLETE
════════════════════════════════════════════════════════════
  Rules added to CLAUDE.md:    [N]
  Lessons added to lessons.md: [N]
  Flagged for manual review:   [N]
  Duplicates skipped:          [N]
  Rule upgrades proposed:      [N]
════════════════════════════════════════════════════════════
```
