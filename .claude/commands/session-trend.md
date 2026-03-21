---
description: Show correction trends and output quality across recent sessions
allowed-tools: Read, Bash, Glob, Grep
---

## Context
- Metrics directory: brain/metrics/
- Sessions directory: brain/sessions/

<!-- EXTENSION POINT: When brain/outcomes/ is populated, add it as a third
     data source here. The scan loop in Step 2 already reads by date key,
     so adding outcomes is: list outcomes/ files, match by date, pull
     tactic/result counts into the per-date record. No structural changes needed. -->

## Your Task

Analyze session metrics and session summaries to show whether the agent is compounding, flat, or regressing.

### Step 1: Load Data Sources

Read all files from both directories, sorted by date (filenames are `[YYYY-MM-DD].md`):

```bash
ls -1 "C:/Users/olive/SpritesWork/brain/metrics/" 2>/dev/null | sort
ls -1 "C:/Users/olive/SpritesWork/brain/sessions/" 2>/dev/null | sort
```

If fewer than 2 metrics files exist:
```
Not enough data for trend analysis. Need at least 2 sessions with metrics.
Run /session-audit at session close to start building metrics.
```

### Step 2: Parse Each Date

For each date found in metrics/, read the metrics file and extract:
- `corrections_received` (from `## Scores`)
- `research_gates_triggered` and `research_gates_completed` (from `## Gate Compliance`)
- `outputs_produced` and `outputs_unedited` (from `## Output Quality`)
- Correction categories (from `## Correction Categories`)

Then check if a matching session summary exists in sessions/ for the same date. If it does, read it and extract:
- Key actions from `## What Was Done`
- Learnings from `## Learnings Applied`
- Open items from `## Open Items`
- Any qualitative notes that explain *why* numbers look the way they do

Build a combined per-date record: `{ date, metrics: {...}, session_notes: "..." }`.

<!-- EXTENSION POINT: Add brain/outcomes/ scan here. For each date, check
     if outcomes were logged. Pull tactic count, positive/negative signal
     ratio, and top outcome types into the per-date record. -->

### Step 3: Compute Trends

Split sessions into two halves (first half vs second half of available data).

**Metric 1: Avg corrections per session**
- First half average vs second half average
- Trend: DOWN = improving, UP = regressing, FLAT = <10% change

**Metric 2: Research gate compliance rate**
- `gates_completed / gates_triggered` as percentage, per half
- Trend: UP = improving, DOWN = regressing, FLAT = <5% change

**Metric 3: Unedited output rate**
- `outputs_unedited / outputs_produced` as percentage, per half
- Trend: UP = improving, DOWN = regressing, FLAT = <5% change

**Metric 4: Top correction categories**
- Aggregate categories across all sessions
- Show top 3 by frequency

**Metric 5: Session summary cross-reference**
- For each date with both metrics and session notes, check if the qualitative notes explain the quantitative scores
- Look for patterns: sessions with high corrections — what was happening? Sessions with high unedited rate — what was different?
- Extract the single most explanatory note across all session summaries

### Step 4: Display Report

```
════════════════════════════════════════════════════════════
SESSION TREND REPORT ([N] sessions analyzed)
════════════════════════════════════════════════════════════

Corrections/session:    [first half avg] → [second half avg]  [DOWN/UP/FLAT]
Gate compliance:        [first half %]   → [second half %]    [UP/DOWN/FLAT]
Unedited output rate:   [first half %]   → [second half %]    [UP/DOWN/FLAT]

Top correction categories:
  1. [CATEGORY] — [count] ([trend note])
  2. [CATEGORY] — [count] ([trend note])
  3. [CATEGORY] — [count] ([trend note])

Verdict: [COMPOUNDING / FLAT / REGRESSING]
  [One sentence explaining why — e.g., "Corrections dropping, gate compliance
  rising, but DRAFTING errors persist. Focus there next session."]

Pattern note: [One sentence from session summaries that explains the trend
  the numbers show — e.g., "High correction sessions correlate with multi-prospect
  days where research steps were abbreviated under time pressure."]
════════════════════════════════════════════════════════════
```

### Verdict Logic

- **COMPOUNDING:** Corrections trending down AND (gate compliance up OR unedited rate up)
- **REGRESSING:** Corrections trending up OR (gate compliance down AND unedited rate down)
- **FLAT:** Everything else — no clear signal in either direction

The pattern note MUST reference specific session summaries, not just restate the numbers. If no session summaries exist for the metrics dates, note: "No session summaries available for cross-reference. Run wrap-up step 10 to start building them."

### Step 5: Actionable Insight

Based on the top correction category that is NOT improving, output one specific recommendation:
```
Focus area: [CATEGORY]
  [Specific recommendation — e.g., "Review soul.md banned words list before drafting.
  3 of last 5 LANGUAGE corrections were banned word usage."]
```
