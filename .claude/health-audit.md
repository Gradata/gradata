# Enterprise Health Audit (v2.1)
# Quick health at startup (automated via hook). Full audit at wrap-up (binary gate).
# Superseded in part by wrap_up_validator.py (15-check binary gate) and session_start_reminder.py (6 automated checks).
# This file retains the FULL wrap-up audit dimensions for manual deep-dives and quarterly reviews.

## Quick Health Check (Session Startup — automated)

Handled by session_start_reminder.py hook. 6 automated checks:
1. Vault accessible (brain/ directory)
2. system.db exists and readable
3. PATTERNS.md exists
4. brain/.git integrity
5. CLAUDE.md line count (<150)
6. events.jsonl exists (auto-creates if missing)

If any CRITICAL: surfaces alert before session loads. No manual intervention needed.

### MCP Connectivity (checked during Phase 1.5 tool scan)
- Gmail MCP responds (test: gmail_get_profile)
- Calendar MCP responds (test: gcal_list_events)
- Apollo MCP responds (test: any search)
- Fireflies MCP responds (test: any search)
- Pipedrive via Composio responds (test: RUBE_SEARCH_TOOLS)
- If any MCP fails -> follow fallback-chains.md, flag to Oliver

### Report Format (startup)
```
HEALTH: [X/6 systems green] | MCPs: [list any down] | Stale: [list any stale deals/emails]
```
One line. If all green, move on. If any red, fix first.

---

## Full Health Audit (Wrap-Up — binary gate)

Primary enforcement: wrap_up_validator.py runs 15 binary checks with 80% threshold.
Auto-fix cycles up to 3 times before escalating.

The validator checks cover:
- Session note exists and has required sections
- Lessons updated if corrections occurred
- Events logged for the session (events.jsonl has entries)
- brain/.git has a session commit
- loop-state.md header matches current session
- startup-brief.md updated
- CLAUDE.md under line limit
- No orphaned files
- Brain Report Card computed (System, AI Quality, Growth, Architecture)

### Supplementary Checks (manual, for quarterly deep-dives)

#### Vault Integrity
- [ ] brain/prospects/ — at least 1 note exists
- [ ] brain/personas/ — at least 1 note exists
- [ ] brain/sessions/ — exists
- [ ] All prospect notes touched this session have updated frontmatter (last_touch, stage, tags)

#### MCP Health
- [ ] Gmail — can list drafts
- [ ] Calendar — can list events
- [ ] Apollo — can search contacts
- [ ] Fireflies — can search transcripts
- [ ] Pipedrive (Composio) — can search tools
- [ ] For each failed MCP: note in session notes, check if it affected outputs

#### Process Compliance
- [ ] Every email drafted went through pre-draft gate
- [ ] Every CRM note published used the correct template
- [ ] Calendar was checked before any task/next-step creation
- [ ] No output was presented below self-score of 7
- [ ] All self-scores logged in session notes

#### Data Hygiene
- [ ] No Pipedrive notes with AI attribution text
- [ ] No Pipedrive notes citing .md files as sources
- [ ] No duplicate notes on any deal

### Report Format (wrap-up)
```
HEALTH AUDIT: [date]
Validator: [X/15 pass] — [list any failures]
Report Card: System [X] | AI Quality [X] | Growth [X] | Arch [X]
MCPs: [X/5 up] — [list any down]
Process: [X/5 compliant] — [list any violations]
OVERALL: [PASS / NEEDS ATTENTION / CRITICAL]
```

---

## Escalation Rules
- Validator passes (80%+) -> session closes normally
- Validator fails -> auto-fix up to 3 cycles -> if still failing, escalate to Oliver
- Any MCP down for 2+ consecutive sessions -> escalate as infrastructure issue
- Credits below 50 -> escalate immediately

## Trend Detection
Track health audit results across sessions via events.jsonl queries:
- Same check failing 3+ sessions -> structural issue, not a one-off
- Same MCP failing 2+ sessions -> connection needs repair
- Process violations repeating -> gate needs redesign
