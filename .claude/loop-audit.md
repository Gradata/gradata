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

## Full Audit Scoring (0-10 each)

### 1. Tag Completeness
Were ALL interactions this session tagged with the full taxonomy (type, channel, intent, tone, angle, framework, sequence_position)?
- 10: Every interaction has every tag, values are from the standard taxonomy
- 7: All interactions tagged, minor inconsistencies in values
- 4: Some interactions tagged, some skipped
- 0: Tags routinely skipped

### 2. Outcome Tracking
Were pending outcomes checked against Gmail? Were outcomes updated accurately?
- 10: Every pending outcome resolved, Gmail checked for all, dates logged
- 7: Most outcomes resolved, 1-2 still pending from previous sessions
- 4: Outcomes checked but not all updated in prospect notes
- 0: Outcomes not checked

### 3. Pattern Application
Did Claude read PATTERNS.md before drafting? Were insights actually used in the output?
- 10: PATTERNS.md read, specific insights cited, approach chosen based on data
- 7: PATTERNS.md read, approach generally aligned with data but not explicitly cited
- 4: PATTERNS.md referenced but insights not clearly applied
- 0: PATTERNS.md not read before drafting

### 4. Learning Capture
Were new data points added to the system? Were PATTERNS.md tables updated at wrap-up?
- 10: Every interaction created a trackable data point. Tables recalculated. New patterns surfaced.
- 7: Data points created but tables not fully recalculated
- 4: Some data logged, tables not updated
- 0: No learning captured

### 5. Angle Rotation
Was angle repetition avoided? Was the 70/30 exploration ratio followed?
- 10: No repeated failed angles. Mix of proven + experimental approaches. Rotation documented.
- 7: No repeated failed angles. Mostly proven approaches, minimal experimentation.
- 4: Some angle repetition. No conscious rotation strategy.
- 0: Same angle repeated despite previous failure.

### 6. Confidence Accuracy
Were confidence levels cited correctly? Were [HYPOTHESIS] patterns presented differently from [PROVEN]?
- 10: Every recommendation includes sample size + confidence level. Hypotheses clearly caveated.
- 7: Confidence levels mentioned but not always with sample sizes
- 4: Confidence levels occasionally cited
- 0: Patterns presented without confidence context

---

## Scoring Thresholds

| Average Score | Rating | Action |
|--------------|--------|--------|
| 9-10 | EXCELLENT | Loop is compounding. Keep going. |
| 8+ | PASS | Session can close. Minor improvements for next session. |
| 7 | BORDERLINE | Fix the lowest dimension before closing. One more cycle. |
| 5-6 | ATTENTION | Multiple fixes needed. Do not close session. |
| 3-4 | CRITICAL | Learning loop is broken. Pause and repair. |
| 0-2 | FAILED | Loop is not running. Rebuild. |

**HARD GATE: Combined score (loop-audit + auditor-system) must average 8.0+ to close session. Below 8 = fix before wrap.**

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
