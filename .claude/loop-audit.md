# Loop Audit — Learning Engine Quick Check

## Purpose
Evaluates Loop data freshness at session start. Deep analysis moved to quarterly_audit.py (runs every 25 sessions).

## Startup Quick Check (3 questions, every session)

1. **Data freshness:** When was PATTERNS.md last updated? If >3 sessions ago, flag.
2. **Pending outcomes:** How many prospect touches have outcome = "pending"? If >5, flag.
3. **Coverage:** What % of active prospects have complete tag data on their last touch? If <80%, flag.

Format: `Loop: [PATTERNS age] | [X pending outcomes] | [X% tagged] — [OK/ATTENTION/CRITICAL]`

## Common Loop Failures and Fixes

| Failure | Root Cause | Fix |
|---------|-----------|-----|
| Same angle repeated on follow-up | Didn't check prospect sequence history | Read prospect note BEFORE drafting |
| PATTERNS.md stale | Wrap-up skipped or no interactions to log | Ensure wrap-up runs every session |
| Tags inconsistent | Free-form values instead of taxonomy | Use LOOP_RULE_5 taxonomy strictly |
| Outcomes never resolved | Gmail not checked at startup | Startup outcome check is mandatory |
| No pipeline tier data | All emails going through Instantly | Use Claude tier for active Pipedrive deals |
| Confidence levels wrong | Sample sizes not tracked | Always cite N alongside % |
| Angle rotation not happening | No conscious strategy | Check PATTERNS.md and prospect history before picking angle |
