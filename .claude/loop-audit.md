# Loop Audit — Learning Engine Quality Assurance

## Purpose
Evaluates Loop's effectiveness as a closed-loop sales intelligence system. Runs as part of the post-session audit. Separate from the general session auditor — this focuses specifically on whether the learning loop is working.

## When It Runs
- **Quick check:** Every session startup (3 lines in status)
- **Full audit:** Every session wrap-up (scored, gaps identified)
- **Deep audit:** Every 10 sessions (system-wide pattern analysis)

---

## Startup Quick Check (3 questions)

1. **Data freshness:** When was PATTERNS.md last updated? If >3 sessions ago, flag.
2. **Pending outcomes:** How many prospect touches have outcome = "pending"? If >5, flag.
3. **Coverage:** What % of active prospects have complete tag data on their last touch? If <80%, flag.

Format: `Loop: [PATTERNS age] | [X pending outcomes] | [X% tagged] — [OK/ATTENTION/CRITICAL]`

---

## Full Audit Scoring

**CONSOLIDATED:** Loop scoring dimensions (Pattern Application, Angle Rotation, Confidence Accuracy) are now in auditor-system.md as dimensions 6-8. They score there alongside the 5 core dimensions. Single 8.0+ gate in auditor-system.md.

This file retains: startup quick-check (above), deep audit (below), and common failure reference.

---

## Deep Audit (Every 10 Sessions)

### Data Quality Analysis
1. How many total data points in PATTERNS.md across all tables?
2. How many angles have crossed from [HYPOTHESIS] to [EMERGING] or higher?
3. How many negative patterns have been identified?
4. Are Pipeline Tier tables accumulating data, or still empty?

### Learning Velocity
1. How many new insights surfaced in the last 10 sessions?
2. Has any [PROVEN] pattern been contradicted by recent data?
3. Are cadence rules being refined based on actual outcome data?
4. Is the system getting measurably smarter (tighter angle selection, better first-draft quality)?

### System Health
1. Are prospect notes consistently structured (template compliance)?
2. Is brain/prospects/ growing with new prospects?
3. Are stale prospects being archived per rules?
4. Is there drift between Pipedrive deal stages and brain/ note stages?

### ROI Indicators
1. Reply rate trend for Claude-written emails (Pipeline Tier)
2. Meeting conversion rate trend
3. Time-to-close trend
4. Angle hit rate improvement over time

---

## Loop Health Dashboard (generated at deep audit)

```
LOOP HEALTH — [Date]
━━━━━━━━━━━━━━━━━━━━━
Data Points:     [X] total ([X] cold tier, [X] pipeline tier)
Active Prospects: [X] with complete Loop data
Patterns:        [X] proven, [X] emerging, [X] hypothesis
Negative Rules:  [X] confirmed failures
Avg Tag Coverage: [X]%
Pipeline Tier:   [X] emails tracked, [X]% reply rate
Cold Tier:       [X] emails tracked, [X]% reply rate
Confidence Gaps: [list angles/personas with [INSUFFICIENT] data]
━━━━━━━━━━━━━━━━━━━━━
VERDICT: [COMPOUNDING / GROWING / STALLED / BROKEN]
```

---

## Common Loop Failures and Fixes

| Failure | Root Cause | Fix |
|---------|-----------|-----|
| Same angle repeated on follow-up | Didn't check prospect sequence history | Read prospect note BEFORE drafting, always |
| PATTERNS.md stale | Wrap-up skipped or no interactions to log | Ensure wrap-up runs every session |
| Tags inconsistent | Free-form values instead of taxonomy | Use LOOP_RULE_5 taxonomy strictly |
| Outcomes never resolved | Gmail not checked at startup | Make startup outcome check mandatory |
| No pipeline tier data | All emails going through Instantly | Use Claude tier for active Pipedrive deals |
| Confidence levels wrong | Sample sizes not tracked | Always cite N alongside % |
| Angle rotation not happening | No conscious strategy | Check PATTERNS.md and prospect history before picking angle |
