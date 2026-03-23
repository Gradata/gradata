---
name: one-step-better
description: Scans session history for personalized improvement tips — checks 8 categories (stale tools, unused vault data, lesson stagnation, etc.) and surfaces the single highest-impact recommendation. Use when the user mentions "one step better", "improvement tip", "what should I improve", "optimization suggestion", "usage patterns", "tip", or wants a personalized recommendation for leveling up their workflow.
---

# /one-step-better

> Scans actual usage patterns from session history, scores personalized
> recommendations by impact and ease, surfaces exactly one actionable tip.
> Records history so it never repeats. Re-scans every 14 sessions.

---

## When to Run

- User invokes `/one-step-better`
- Suggested at end of working sessions during weeks 1-4 (before compounding kicks in)
- Never runs during setup sessions

## Execution Steps

### Step 1: Gather Data

Read the following files to understand usage patterns:

1. **docs/Session Notes/** — last 14 session notes (or all available if fewer)
2. **.claude/lessons.md** — active lessons, graduation rate, stuck lessons
3. **brain/system-patterns.md** — audit scores, gate performance, tool failures
4. **workflows/detection-log.md** — detected patterns, saved workflows
5. **skills/one-step-better/tip-history.md** — previously delivered tips

### Step 2: Score Recommendations

Scan 8 categories. For each, check if a recommendation exists and score it:

#### Categories

1. **Repeated Corrections**
   - Signal: same correction type appears 2+ times in lessons.md
   - Tip template: "Your agent keeps [error pattern]. Add this to your hard constraints to prevent it: [specific rule]."
   - Impact: 4-5 (prevents recurring quality failures)
   - Ease: 5 (one line added to soul.md or CARL)

2. **Unused Tools**
   - Signal: tool configured in context-manifest.md but zero calls in 14 sessions
   - Tip template: "You have [tool] connected but haven't used it. Next time you [task type], try [specific use case]."
   - Impact: 2-3 (efficiency gain, not critical)
   - Ease: 4 (just try it next time)

3. **Skipped Steps**
   - Signal: gate steps with 0 catches in system-patterns.md over 14+ runs
   - Tip template: "Step [N] of your [gate] hasn't caught anything in [N] sessions. Consider removing it to save time, or tightening it to catch more."
   - Impact: 2 (time savings)
   - Ease: 5 (delete one line)

4. **Missing Workflows**
   - Signal: 3+ matches in detection-log.md without a saved workflow
   - Tip template: "You do [task] almost every session. Saving it as a workflow would make it consistent and seed 5 quality lessons."
   - Impact: 4 (consistency + learning acceleration)
   - Ease: 3 (requires 5 min to review and confirm)

5. **Quality Drift**
   - Signal: self-scores trending down on a dimension in system-patterns.md (3+ session decline)
   - Tip template: "Your [dimension] scores have dropped from [X] to [Y] over [N] sessions. The likely cause is [pattern]. Try [specific fix]."
   - Impact: 5 (quality is the product)
   - Ease: 3 (requires behavioral change)

6. **Lesson Stagnation**
   - Signal: lessons at INSTINCT for 10+ sessions without firing (TRACK:0/3)
   - Tip template: "These [N] lessons haven't been tested in [N] sessions. They're either untestable or too narrow. Consider rewriting or removing: [list]."
   - Impact: 2 (system hygiene)
   - Ease: 4 (review and delete)

7. **Tool Failure Patterns**
   - Signal: same tool failing 3+ times in system-patterns.md fallback chain data
   - Tip template: "Switch your primary [action] tool from [X] to [Y] — [Y] has been more reliable in your sessions ([X] failed [N] times, [Y] succeeded [N] times)."
   - Impact: 3 (reliability)
   - Ease: 5 (swap one line in fallback-chains.md)

8. **Session Efficiency**
   - Signal: startup consistently takes 3+ minutes (tracked in session notes)
   - Tip template: "Your startup is loading [file/check] that hasn't surfaced useful info in [N] sessions. Move it from Tier 1 to Tier 2 in context-manifest.md."
   - Impact: 3 (time savings every session)
   - Ease: 5 (move one line between tiers)

### Step 3: Rank and Select

```
Score = Impact × Ease (max 25)
```

- Filter out tips already in tip-history.md
- Filter out categories with insufficient data (< 3 sessions of evidence)
- Select highest-scoring remaining tip
- If multiple tie: prefer the category with the most evidence (highest data point count)

### Step 4: Present

```
## One Step Better

[One sentence describing the pattern observed]
[One sentence describing the specific action to take]
[One sentence describing the expected improvement]

Impact: [X/5] | Ease: [X/5] | Score: [X/25]
```

### Step 5: Record

Append to `skills/one-step-better/tip-history.md`:

```
| Date | Session | Category | Tip Summary | Score | Acted On? |
```

"Acted On?" starts as "pending" — updated at next scan if the user implemented the change.

---

## Re-scan Cadence

- First 14 sessions: scan every session (user is new, patterns forming fast)
- After session 14: scan every 14 sessions
- If user invokes `/one-step-better` manually: always scan regardless of cadence

## Tip History File

Created automatically on first run at `skills/one-step-better/tip-history.md`.

```markdown
# One Step Better — Tip History

| Date | Session | Category | Tip Summary | Score | Acted On? |
|------|---------|----------|-------------|-------|-----------|
```
