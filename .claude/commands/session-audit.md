---
description: End-of-session close routine — reflect, log outcomes, write summary, propose upgrades
allowed-tools: Read, Edit, Write, Bash, Grep, Glob, AskUserQuestion, TodoWrite
---

## Context
- CLAUDE.md: @CLAUDE.md
- Lessons: @.claude/lessons.md
- Learnings queue: !`python .claude/hooks/reflect/scripts/read_queue.py 2>/dev/null || echo "[]"`

## Your Task

Run the end-of-session close routine. This combines /reflect with outcome logging and rule upgrade proposals.

### Step 1: Run /reflect

Process any queued learnings using the reflect routing logic:
- Behavioral rules → CLAUDE.md
- Specific mistakes → .claude/lessons.md
- Methodology insights → flag for manual review

Check queue:
```bash
python .claude/hooks/reflect/scripts/read_queue.py 2>/dev/null || echo "[]"
```

If queue has items, process them using the /reflect workflow (classify, dedupe, route, apply).
If queue is empty, note "No queued learnings" and continue.

### Step 2: Log Session Outcomes

Review what happened this session and prompt for outcome logging:

```
What outcomes should we log from this session?
Examples:
  - "Sent follow-up to Hassan — gap selling angle, awaiting reply"
  - "Cold call to Jennifer — voicemail, will retry Thursday"
  - "Filtered 200 leads — 27 TIER1 qualified"

Enter outcomes (one per line, blank to skip):
```

For each outcome, run the /log-outcome logic (format, route, pattern-check).

### Step 3: Write Session Summary

Create `brain/sessions/[YYYY-MM-DD].md` with:

```markdown
# Session Summary — [DATE]

## What Was Done
- [bullet list of key actions taken]

## Outcomes Logged
- [outcomes from step 2]

## Learnings Applied
- [rules/lessons from step 1]

## Open Items
- [anything unfinished or pending]

## Rule Upgrade Candidates
- [from step 4, if any]
```

### Step 4: Propose Rule Upgrades

Scan .claude/lessons.md for clusters of 3+ similar corrections:

1. Group lessons by CATEGORY
2. Within each category, look for semantically similar entries
3. If 3+ similar lessons exist, propose consolidation into a CLAUDE.md rule:

```
════════════════════════════════════════════════════════════
RULE UPGRADE CANDIDATES
════════════════════════════════════════════════════════════

1. CATEGORY: [name] (3 similar lessons found)
   Lessons:
   - [lesson 1]
   - [lesson 2]
   - [lesson 3]

   Proposed CLAUDE.md rule:
   "[synthesized universal rule]"

   Promote to CLAUDE.md? [y/n]
════════════════════════════════════════════════════════════
```

If promoted:
- Add rule to appropriate CLAUDE.md section
- Mark the source lessons as graduated in lessons.md
- Move them to lessons-archive.md

### Step 5: Write Session Metrics

Create `brain/metrics/[YYYY-MM-DD].md` with standardized format:

```markdown
---
date: [YYYY-MM-DD]
session: [N]
---

## Scores
- corrections_received: [count of corrections Oliver gave this session]
- corrections_queued: [count of items in reflect queue at session end]
- outcomes_logged: [count of outcomes logged in step 2]
- rule_upgrades_proposed: [count from step 4]
- rule_upgrades_applied: [count promoted to CLAUDE.md]

## Gate Compliance
- research_gates_triggered: [count of gates that should have fired]
- research_gates_completed: [count fully completed with all steps]
- gates_skipped: [list any skipped gates or "none"]

## Output Quality
- outputs_produced: [count of major outputs — emails, call scripts, lead lists, CRM updates]
- outputs_unedited: [count Oliver approved without changes]
- outputs_revised: [count Oliver asked to revise]
- avg_self_score: [average of self-scores given this session, or "N/A"]

## Correction Categories
- [CATEGORY]: [count] — [brief pattern note]
```

This format is consistent with brain/sessions/ (date-keyed, frontmatter with session number) so /session-trend can scan both in one pass.

### Step 6: Summary

```
════════════════════════════════════════════════════════════
SESSION AUDIT COMPLETE (Steps 1-5 of 11)
════════════════════════════════════════════════════════════
  Learnings processed:     [N]
  Outcomes logged:         [N]
  Session summary:         brain/sessions/[date].md
  Session metrics:         brain/metrics/[date].md
  Rule upgrades proposed:  [N]
  Rule upgrades applied:   [N]
════════════════════════════════════════════════════════════
```

### Step 7: MANDATORY — Cross-Check CLAUDE.md Wrap-Up Steps

**This skill covers steps 7, 10, and partial 1. The following CLAUDE.md steps are NOT covered by this skill and MUST run separately. Check each one:**

```
[ ] Step 0.5 — User Summary (in session note)
[ ] Step 1   — Daily notes (brain/sessions/)
[ ] Step 8   — Post-session audit (.claude/auditor-system.md + .claude/loop-audit.md)
[ ] Step 9   — Event connection verification (query events.jsonl for session signals)
[ ] Step 9.5 — Git checkpoint (brain/ commit + VERSION.md increment)
[ ] Step 10.5— Startup brief refresh (domain/pipeline/startup-brief.md)
[ ] Step 11  — Handoff (rewrite brain/loop-state.md)
[ ] Step 11b — Agent Distillation (agents/registry.md → updates/)
```

**Do NOT declare wrap-up complete until every box is checked. This skill is a subset, not a replacement.**
