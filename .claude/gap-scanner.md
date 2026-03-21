# Gap Scanner — Proactive System Integrity Checker

> Runs at startup and after every 3rd major action mid-session.
> Detects disconnected systems, skipped tools, and process drift BEFORE Oliver notices.

## Startup Scan (runs during Phase 0.5 of session-start)

### System Connectivity Check
For each tool/system, verify it's reachable and has been used recently:

| System | Check | Alert If |
|--------|-------|----------|
| Brain vault | brain/prospects/ readable, >0 files | 0 files = CRITICAL |
| Knowledge graph | system.db has entities table with >0 rows | 0 entities = seed needed |
| PATTERNS.md | exists and updated within last 3 sessions | stale >3 sessions = WARNING |
| NotebookLM (tier system: .claude/skills/notebooklm/SKILL.md) | last query logged in canonical_logs | never queried = WARNING |
| Analytics DB | system.db tables exist and have data | empty tables = WARNING |
| Persona MOCs | brain/personas/ has >0 files | 0 MOCs = CRITICAL |
| Experiments | any RUNNING experiments in experiment tracker | 0 running = INFO (start one) |
| Humanizer | skill installed at ~/.claude/skills/humanizer | missing = CRITICAL |

### Process Drift Detection
Check if recent sessions show signs of skipping:

| Pattern | How to Detect | Alert Level |
|---------|--------------|-------------|
| Vault skipped | canonical_logs show prospect actions without vault_checked=true | CRITICAL |
| NotebookLM skipped | canonical_logs show 3+ prospect actions, 0 notebooklm queries | WARNING |
| Knowledge graph stale | No new entities added in 3+ sessions | INFO |
| No experiments running | 0 active experiments for 5+ sessions | INFO |
| Calibration silent | 0 score overrides in 5+ sessions | INFO (prompt Oliver) |
| Pre-flight skipped | Any prospect output without pre-flight block | CRITICAL |

## Mid-Session Scan (runs after every 3rd major action)

Quick check — 3 questions:
1. Am I about to present prospect output? → Did pre-flight run?
2. Have I used the vault this session for any prospect work? → If not, why?
3. Have I queried NotebookLM for any research task? → If not, should I?

If any answer suggests a gap: surface immediately.
"GAP ALERT: [what's missing] — [why it matters] — [fixing now]"

## Proactive Alerts (surface to Oliver without being asked)

### Every Session:
- "SYSTEM: [X] of [Y] systems connected. [list any disconnected]"
- "GAPS: [list any detected gaps from startup scan]"

### Every 3rd Session:
- "USAGE: NotebookLM queried [X] times in last 3 sessions. Knowledge graph has [Y] entities. [Z] experiments running."
- If any number is 0: "RECOMMENDATION: [specific action to take]"

### On Detection:
- If pre-flight was about to be skipped: "BLOCKED: Pre-flight not completed. Running now before presenting output."
- If vault exists but wasn't read: "WARNING: Prospect note exists for [Name] but wasn't read. Reading now."
- If NotebookLM has relevant data but wasn't queried: "MISSED: NotebookLM has [X] sources for this persona. Querying now."

## Integration with Analytics
Log every gap detection to system.db via analytics.py:
```
python analytics.py log-rule GAP_SCANNER loop [session] applied "[gap description]"
```

Track: gaps_detected, gaps_auto_fixed, gaps_escalated_to_oliver
