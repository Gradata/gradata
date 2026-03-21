# Enterprise Health Audit
# Runs at session startup (quick) and wrap-up (full). Catches system rot before it compounds.

## Quick Health Check (Session Startup — 10 seconds)
Run automatically before responding. Pass/fail only. If any FAIL, fix before proceeding.

### Core Files
- [ ] CLAUDE.md readable and <150 lines
- [ ] .claude/lessons.md readable and <30 entries
- [ ] .claude/gates.md readable
- [ ] docs/startup-brief.md readable
- [ ] brain/README.md readable (vault accessible)

### MCP Connectivity
- [ ] Gmail MCP responds (test: gmail_get_profile)
- [ ] Calendar MCP responds (test: gcal_list_events)
- [ ] Apollo MCP responds (test: any search)
- [ ] Fireflies MCP responds (test: any search)
- [ ] Pipedrive via Composio responds (test: RUBE_SEARCH_TOOLS)
- [ ] If any MCP fails → note which one, follow fallback-chains.md, flag to Oliver

### Data Freshness
- [ ] Daily note exists for yesterday or last session date
- [ ] audit-log.md has entry for last session
- [ ] email-tracking.md has no "Pending" entries older than 7 days (check for replies)
- [ ] lessons.md has no entries older than 30 days without graduation review

### Pipeline State
- [ ] Pipedrive deals pulled (Oliver tag 45)
- [ ] No deal has zero upcoming activities
- [ ] No deal stuck in same stage 14+ days without a flag

### Report Format (startup)
```
HEALTH: [X/5 systems green] | MCPs: [list any down] | Stale: [list any stale deals/emails]
```
One line. If all green, move on. If any red, fix first.

---

## Full Health Audit (Wrap-Up — 60 seconds)
Runs as part of the smoke test step. More thorough than startup.

### 1. File Integrity
- [ ] CLAUDE.md — readable, <150 lines, last modified date matches changelog
- [ ] .claude/gates.md — readable, all 8 gates present
- [ ] .claude/pipedrive-templates.md — readable, all 5 templates present
- [ ] .claude/quality-rubrics.md — readable, all 4 output types scored
- [ ] .claude/fallback-chains.md — readable, all 7 tool chains present
- [ ] .claude/auditor-system.md — readable, all sections present
- [ ] .claude/lessons.md — <30 entries, no entries >30 days old without review
- [ ] .claude/lessons-archive.md — exists, graduated entries have criteria noted
- [ ] .claude/audit-log.md — last entry matches current session
- [ ] .claude/changelog.md — last entry matches most recent CLAUDE.md change
- [ ] .claude/review-queue.md — no items >7 days old without Oliver's response
- [ ] .claude/weekly-pulse-template.md — exists

### 2. Vault Integrity
- [ ] brain/README.md — readable, structure matches actual folders
- [ ] brain/prospects/ — at least 1 note exists
- [ ] brain/personas/ — at least 1 note exists
- [ ] brain/objections/ — at least 1 note exists
- [ ] brain/competitors/ — at least 1 note exists
- [ ] brain/templates/ — at least 1 note exists
- [ ] brain/demos/ — at least 1 note exists
- [ ] brain/pipeline/email-tracking.md — exists, has entries
- [ ] brain/sessions/ — exists
- [ ] All prospect notes touched this session have updated frontmatter (last_touch, stage, tags)

### 3. MCP Health
- [ ] Gmail — can list drafts
- [ ] Calendar — can list events
- [ ] Apollo — can search contacts
- [ ] Fireflies — can search transcripts
- [ ] Pipedrive (Composio) — can search tools
- [ ] For each failed MCP: note in daily notes, check if it was down during session (affected outputs?)

### 4. Composio Credit Check
- [ ] Estimate credits used this session (count RUBE calls)
- [ ] Estimate remaining budget for the month
- [ ] If <200 remaining → flag to Oliver, switch to read-only mode for Pipedrive
- [ ] If <50 remaining → CRITICAL: only essential writes (deal stage changes, demo notes)

### 5. Process Compliance
- [ ] Every email drafted this session went through pre-draft gate
- [ ] Every CRM note published used the correct template
- [ ] Every Fireflies search used multi-term pattern (email + name + company)
- [ ] Calendar was checked before any task/next-step creation
- [ ] No output was presented below self-score of 7
- [ ] All self-scores logged in daily notes

### 6. Data Hygiene
- [ ] No Pipedrive notes with "Not confirmed" or "pending" flags
- [ ] No Pipedrive notes with AI attribution text
- [ ] No Pipedrive notes citing .md files as sources
- [ ] No duplicate notes on any deal
- [ ] All contacts touched have email + phone in Pipedrive (or flagged as missing)

### 7. Learning System
- [ ] All corrections from this session logged to lessons.md
- [ ] Vault updated for every prospect touched
- [ ] Email tracking updated for every email drafted/sent
- [ ] Changelog updated if CLAUDE.md was modified
- [ ] Audit log entry written for this session

### Report Format (wrap-up)
```
HEALTH AUDIT: [date]
Files: [X/12 pass] — [list any failures]
Vault: [X/10 pass] — [list any gaps]
MCPs: [X/5 up] — [list any down]
Credits: [X used today] / [~X remaining this month]
Process: [X/6 compliant] — [list any violations]
Data: [X/5 clean] — [list any issues]
Learning: [X/5 captured] — [list any gaps]
OVERALL: [PASS / NEEDS ATTENTION / CRITICAL]
```

---

## Escalation Rules
- 1-2 failures → fix silently, note in daily notes
- 3-5 failures → flag to Oliver at end of wrap-up
- 6+ failures → CRITICAL: stop wrap-up, address immediately, Oliver must be informed
- Any MCP down for 2+ consecutive sessions → escalate as infrastructure issue
- Credits below 50 → escalate immediately

## Trend Detection
Track health audit results across sessions:
- Same file failing 3+ sessions → structural issue, not a one-off
- Same MCP failing 2+ sessions → connection needs repair
- Credits consistently high → review batching strategy
- Process violations repeating → gate isn't working, needs redesign
