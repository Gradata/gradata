# Self-Audit — Compounding Intelligence Review

> The mechanism that turns accumulated data into expertise.
> Without this, the brain gets bigger. With it, the brain gets smarter.
> Runs every 10 sessions. Triggered by periodic-audits.md or manually.
> Never auto-edits CLAUDE.md, CARL, or any core file. Surfaces and waits.
> SDK-portable (brain methodology). Output files are brain layer.

## When This Runs

- Every 10 sessions (checked at wrap-up via periodic-audits.md)
- Wrap-up outputs a reminder. Run before closing or first thing next session.
- Can also be triggered manually anytime ("run self-audit" / "run lens 2")
- Each lens can run independently if time is short.

## Pre-Audit Data Check

Before running any lens, assess data sufficiency. Report honestly:

```
SELF-AUDIT DATA CHECK
  Metrics files:        [N] (need 5+ for rolling averages)
  Outcome entries:      [N] (need 20+ for pattern detection)
  Decision journals:    [N] sessions with entries (need 3+)
  Active lessons:       [N] / Graduated: [N]
  Sessions since last:  [N]
```

If a lens has insufficient data, say so and skip it. Don't manufacture insights from noise.

---

## Lens 1: Error Pattern Analysis

**What it does:** Reads all corrections from the last 10 sessions and finds what's changing and what's stuck.

### Input
- `.claude/lessons.md` — active and graduated lessons with categories, dates, root causes
- `brain/metrics/*.md` — correction counts and categories per session
- `brain/self-model.md` — current blind spots and reliability scores
- Previous self-audit entries in `brain/vault/judgment-calibration.md` (if they exist)

### Process

**Step 1: Classify every correction by error type.**

Not just CATEGORY (DRAFTING, CRM, PROCESS) — that's what went wrong. Error TYPE is why it went wrong:

| Error Type | Meaning | Example |
|-----------|---------|---------|
| DATA_GAP | Didn't have the information | Research didn't surface prospect's ad spend |
| PATTERN_FAILURE | Had the data, read it wrong | Saw agency title but assumed in-house workflow |
| CONFIDENCE_ERROR | Right analysis, wrong certainty | Said "90% sure" but was guessing |
| PROCESS_SKIP | Didn't follow own protocol | Skipped playbook loading before cheat sheet |
| COMMUNICATION_ERROR | Right work, wrong delivery | Used jargon Oliver doesn't want |
| NOVEL_SITUATION | No pattern existed yet | First time encountering this prospect type |

**Step 2: Trend the error types across the 10-session window.**

For each type: count in first 5 sessions vs last 5 sessions. Decreasing = learning is working. Flat = fixes aren't sticking. Increasing = something is degrading.

**Step 3: Detect double-loop candidates.**

If 3+ single-loop corrections exist in the same category without aggregate improvement (the same kinds of mistakes keep happening despite individual fixes), flag it. The individual fixes are treating symptoms — the underlying assumption needs to change.

Present as:
```
DOUBLE-LOOP CANDIDATE: [CATEGORY]
  Corrections: [list the 3+ corrections]
  Individual fixes applied: [what was done each time]
  Why they didn't stick: [the underlying assumption that's wrong]
  Proposed assumption change: [what should change at the model level]
  ⚠ Requires manual approval — this would change how the system thinks, not just what it does.
```

**Step 4: Surface promotion candidates.**

Correction clusters (3+ similar) that should become permanent CLAUDE.md rules. Same mechanic as /reflect Step 8, but with error type context added. Don't duplicate /reflect's scan — reference it. Add the error type classification as new information.

### Output

```
ERROR PATTERN ANALYSIS (Sessions [N] through [N])
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Error Type Trends (first 5 → last 5 sessions):
  DATA_GAP:           [N] → [N]  [↓ ↑ →]
  PATTERN_FAILURE:    [N] → [N]  [↓ ↑ →]
  CONFIDENCE_ERROR:   [N] → [N]  [↓ ↑ →]
  PROCESS_SKIP:       [N] → [N]  [↓ ↑ →]
  COMMUNICATION_ERROR:[N] → [N]  [↓ ↑ →]
  NOVEL_SITUATION:    [N] → [N]  [↓ ↑ →]

Eliminated error types: [any that hit 0 in the last 5 sessions]
Persistent error types: [any flat or increasing despite fixes]

Double-loop candidates: [N] (details below if any)
Promotion candidates:   [N] (details below if any)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

All promotion candidates wait for Oliver's explicit approval. Never auto-edit.

---

## Lens 2: Outcome Retrospective

**What it does:** Reads all logged tactic-to-result entries and finds what's working, what's failing, and where confidence doesn't match reality.

### Input
- `brain/emails/PATTERNS.md` — reply rates by angle, tone, persona, sequence position
- Prospect notes in `brain/prospects/*.md` — individual outcome histories
- `brain/metrics/*.md` — outcomes_logged counts
- `/log-outcome` entries (wherever they're stored)
- Previous retrospective entries in `brain/vault/outcome-retrospectives.md` (if they exist)

### Process

**Step 1: Win/loss by decision type.**

Group outcomes by category (outreach angle, follow-up timing, demo approach, objection handling). For each: win rate, sample size, confidence tier.

**Step 2: Confidence calibration.**

For decisions where confidence was logged (decision journals, self-scores), compare stated confidence to actual outcome. Are we overconfident? Underconfident? In which categories?

**Step 3: Sustain/Improve split.**

Explicitly identify what to keep doing (sustain), not just what to fix (improve). This prevents regression on strengths while chasing weaknesses.

### Output

Synthesize a maximum of 5 insight statements. Each must be:
- Grounded in data (cite the numbers)
- Actionable (what should change or continue)
- Honest about sample size (don't claim a pattern from 3 data points)

Format:
```
OUTCOME RETROSPECTIVE — [DATE]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Data: [N] outcomes analyzed across [N] sessions

SUSTAIN (keep doing):
1. [insight with data]

IMPROVE (change this):
2. [insight with data]

CALIBRATION:
3. [where confidence matched/diverged from reality]

[max 5 total insights]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Append to `brain/vault/outcome-retrospectives.md` under today's date. Never overwrite previous entries.

---

## Lens 3: Judgment Calibration

**What it does:** Reads the last 3 session notes, pulls out decisions, and evaluates whether they were good decisions given what the brain knew at the time.

This is the core differentiator. It's what separates a brain that has accumulated data from one that has developed expertise.

### Input
- Last 3 session notes (`docs/Session Notes/*.md`) — decision journals
- `brain/self-model.md` — what the brain knew about its own strengths/weaknesses
- `brain/loop-state.md` — pipeline state at the time
- `.claude/lessons.md` — what lessons were active at the time
- `brain/vault/judgment-calibration.md` — previous calibration entries (for trend)

### Process

For each decision found in a decision journal:

**1. Intent vs Actual**
What was the decision trying to achieve? What actually happened? If the outcome isn't known yet, note it as pending — don't evaluate what can't be evaluated.

**2. Counterfactual**
Given everything in the brain at the time (not hindsight — what was actually available), was there a better option? Check: did the brain have a lesson, a pattern, or a vault entry that pointed to a different choice? If yes, the decision ignored available knowledge. If no, the decision was the best available.

**3. Confidence accuracy**
Was the stated confidence level justified? If confidence was "HIGH" and the decision was wrong, that's overconfidence. If confidence was low and the decision was right, that's underconfidence. Both are calibration data.

**4. Error type (if suboptimal)**
Same taxonomy as Lens 1. Was it a data gap, pattern failure, confidence error, process skip, or novel situation?

### Output

Per-decision evaluation, structured for trend analysis across cycles:

```
JUDGMENT CALIBRATION — [DATE]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sessions reviewed: [S#], [S#], [S#]
Decisions evaluated: [N]

Decision 1: [one-line description]
  Session: [N] | Confidence: [stated] | Outcome: [result or PENDING]
  Counterfactual: [was a better option available in the brain?]
  Verdict: OPTIMAL / SUBOPTIMAL / PENDING
  Error type: [if suboptimal] | Learning: [what this reveals]

Decision 2: ...

CALIBRATION SUMMARY:
  Decisions evaluated:    [N]
  Optimal:               [N] ([%])
  Suboptimal:            [N] ([%])
  Pending outcome:       [N]
  Overconfident:         [N] (stated high, was wrong)
  Underconfident:        [N] (stated low, was right)
  Knowledge-available-but-ignored: [N] (brain had the answer, didn't use it)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Append to `brain/vault/judgment-calibration.md` under today's date. Never overwrite previous entries.

### Trend tracking (after 3+ cycles)

When enough calibration entries exist, add a trend section:

```
JUDGMENT TREND (across [N] audit cycles):
  Optimal decision rate: [first cycle]% → [latest cycle]%  [↑↓→]
  Overconfidence rate:   [first]% → [latest]%  [↑↓→]
  Knowledge utilization: [first]% → [latest]%  [↑↓→]
```

This trend IS the proof of expertise. It's what shows a renter that this brain's judgment has improved over time, not just that it has more data.

---

## Post-Audit

After all lenses complete:

1. **Update self-model.md** — adjust reliability scores and blind spots based on findings. Surface only, don't auto-write. Ask Oliver to confirm changes.
2. **Feed CQ** — Lens 1 error trends feed Correction Decay. Lens 2 patterns feed Knowledge Utilization. Lens 3 judgment accuracy feeds Lesson Hit Rate and Autonomy Trend. Note which CQ dimensions were affected.
3. **Log run** — add entry to periodic-audits.md with `last_run` session number.

```
SELF-AUDIT COMPLETE — Session [N]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Lens 1 (Error Patterns):    [RAN / SKIPPED — reason]
Lens 2 (Outcomes):          [RAN / SKIPPED — reason]
Lens 3 (Judgment):          [RAN / SKIPPED — reason]
Promotion candidates:       [N] (awaiting approval)
Double-loop candidates:     [N] (awaiting approval)
Insight statements:         [N] appended to vault
Judgment decisions reviewed: [N]
CQ dimensions affected:     [list]
Next self-audit due:        Session [N+10]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Rules

- Never auto-edits CLAUDE.md, CARL, lessons.md, or any core file
- Surfaces candidates and insights only — all changes require Oliver's explicit approval
- Reports data sparsity honestly — won't generate insights from insufficient data
- Each lens can run independently (specify "run lens 3" for just judgment calibration)
- Append-only to vault files — never overwrites previous entries
- If a lens finds nothing meaningful, it says "no actionable findings" — not filler
