---
name: session-start
description: Use when user wants to Run automatically at every session start before responding to Oliver's first message. Loads domain/pipeline/startup-brief.md, lessons.md, CARL, and checks Google Calendar. Defers all other context to on-demand loading based on task intent. Use this skill whenever a new session begins, the user says "start up", "load context", or any time CLAUDE.md's session startup instructions need to execute. This is mandatory — never skip it.
---

# Session Startup (Lazy Load)

Run automatically at session start. Optimized to minimize token cost. Everything not loaded here is available on demand via file pointers in domain/pipeline/startup-brief.md.

## Phase -1: DELTA_SCAN (Brain Alert System)

Run FIRST, before any context loads. Compare current state to previous session snapshot.

1. **Read C:/Users/olive/SpritesWork/brain/loop-state.md** — this is the previous session's handoff snapshot.
2. **Prospect overdue scan** — for every prospect with a `next_touch` date, check if that date is 2+ sessions overdue (approximate: 2+ calendar days since the `next_touch` date). Flag any matches.
3. **Angle failure scan** — for every prospect in brain/prospects/, check if any outreach angle has 3+ consecutive no-replies in sequence. Flag any matches.
4. **Deal stagnation scan** — cross-reference Pipedrive deal stages (from loop-state.md pipeline snapshot or brain/forecasting.md). Flag any deal that has not moved stages in 14+ calendar days.
5. **Output** — if any findings, output the top 3 most urgent as:
   ```
   🧠 BRAIN ALERT [1/3]: [Prospect] overdue for contact by [N] sessions — last touch [date], next_touch was [date]
   🧠 BRAIN ALERT [2/3]: [Prospect] — [angle] angle has [N] consecutive no-replies, rotate approach
   🧠 BRAIN ALERT [3/3]: [Deal/Company] stuck in [stage] for [N] days — needs intervention
   ```
   If nothing anomalous: `"Brain clean — no alerts"`
6. These alerts display BEFORE the session status block, so Oliver sees them immediately.

## Phase 0: Stale Brief Detection

Before loading anything:
1. **Check brain/morning-brief.md** — if it exists and is fresh (< 4 hours old), read it. It contains Gmail replies, Fireflies recordings, Pipedrive changes, pre-drafted follow-ups, and deal health alerts. Skip Gmail/Fireflies scans in Phase 1.5. If stale or missing, Gmail/Fireflies/Pipedrive checks run inline during Phase 1.5.
2. Check modification dates on domain/pipeline/startup-brief.md, lessons.md, Leads/STATUS.md, brain/prospects/
3. If any file was modified AFTER the last session's daily note timestamp → surface changes to Oliver ("Since last session: follow-up checker flagged 2 stale prospects, startup-brief updated by scheduled task")
4. **Staleness sensor** — scan brain files that should be updated regularly. Flag any modified more than 7 days ago: brain/loop-state.md (should update every session), domain/pipeline/startup-brief.md (every session), brain/emails/PATTERNS.md (every prospect session), brain/system-patterns.md (every 5 sessions). Surface stale files as a priority signal: "STALE: [file] last updated [N] days ago — update this session."
5. **Emit session init event** — call `python brain/scripts/events.py` or use events.emit() to log: `HEALTH_CHECK, "session-start", {"stale_files": [...], "brain_alerts": N}`.

## Phase 0.5: System Heartbeat

Quick health pulse before loading context. **Run steps 1-4 + 7 as a single parallel batch** — they are independent file checks with no dependencies between them.

**PARALLEL BATCH (all at once):**
1. Check brain/system.db exists and is readable (SQLite backing store)
2. Check brain/.git exists (version control active)
3. Check domain/carl/loop file size hasn't changed unexpectedly (rule tampering detection)
4. Check CLAUDE.md line count is under 150 (bloat detection)
7. **System Health** — session_start_reminder.py hook runs 6 automated checks (vault, DB, PATTERNS, git, CLAUDE.md lines, events.jsonl). Surfaces CRITICAL/WARNING alerts automatically.
8. **Brain launch check** — run `python brain/scripts/launch.py --json`. Validates header consistency (session numbers match across loop-state + startup-brief), staleness, inter-session modifications, and RAG graduation status. Surface any issues in startup output. If `rag_graduation_ready`, prompt user to activate embedding layer.

9. **Periodic audit check** — session_start_reminder.py hook queries `periodic_audits` SQLite table automatically. Due audits surfaced in startup output. After running an audit, update: `UPDATE periodic_audits SET last_run_session=N, next_due_session=N+frequency WHERE audit_name='...'`

**THEN (sequential, after batch completes):**
5. If any check fails -> surface immediately: "SYSTEM ALERT: [what failed]"
6. **Truth Protocol active** — .claude/truth-protocol.md governs all session output. No success claims without evidence. Verify every tool output. Cite every data source.

This takes <2 seconds. It catches file corruption, accidental deletions, and system drift before they compound.

## Phase 1: Core (~5k tokens)

1. **CLAUDE.md** — auto-loaded by Claude Code. AIOS rules, session flow, work style. Domain config in domain/DOMAIN.md (ICP, tool stack, email frameworks).

**PARALLEL BATCH (steps 2, 3, 4 — no dependencies between them, fire all at once):**
2. **Read domain/pipeline/startup-brief.md** — pipeline snapshot, active campaigns, top lessons, file pointers, credit balances. Read the **Handoff** section first — it tells you exactly where last session left off and what to do first.
3. **Read .claude/lessons.md** — mistakes log. Scan every entry. Never repeat a logged mistake.
4. **Check Google Calendar for today + tomorrow** — surface demos, calls, meetings.

## Phase 1.5: Tool Data + Pipeline Prep

> Data is pulled automatically by the SessionStart hook (api_sync.py → Pipedrive, Gmail,
> Calendar, Instantly, Fireflies). DO NOT re-query these via MCP — read from sync_state/system.db.
> MCP is the FALLBACK if api_sync.py failed (check sync_state timestamps).

Load `domain/carl/loop` rules for this phase.

**Step 5+7: Prospect loading (two tiers)** — Read startup-brief pipeline section. Prospects with meeting/demo/follow-up due within 48h = **Tier 1** (read full brain/prospects/ file). All others = **Tier 2** (load on demand when Oliver names them). For Tier 1, check: (a) `next_touch` dates <= today, (b) untagged touches.

**Step 9: Check brain/signals.md** — unprocessed signals with `relevance >= 7`.

**Step 10: Read api_sync results** — Run `python brain/scripts/api_sync.py status` to check last sync. If sync ran this session (session-init-data.js hook), read results from sync_state table:
```python
import sys; sys.path.insert(0, 'C:/Users/olive/SpritesWork/brain/scripts')
from api_sync import sync_all, format_summary, get_last_sync
syncs = get_last_sync()
# If any source is stale (>24h), re-sync just that source
```
Only fall back to MCP tools if api_sync.py failed or sync_state is missing.

**Step 11: Outcome check** — for EVERY prospect with `outcome: pending`, check Gmail sync results for replies from prospect emails. Reply found → update outcome via delta_tag.py. No reply + next_touch passed → "no-reply". Log outcomes:
   `python brain/scripts/delta_tag.py log-outcome --prospect "[NAME]" --prep-type "email_draft" --outcome "reply|no_reply" --days [DAYS]`

**Step 12: Auto-draft follow-ups** — Read brain/Follow-Up Tracker.md (materialized by hook). For every prospect with a touch due TODAY:
    a. Load the prospect file from brain/prospects/
    b. Determine which cadence track (A or B) and which touch number
    c. Auto-draft the follow-up email using cadence playbook + prospect context + PATTERNS.md
    d. Present drafts to Oliver for review. Never auto-send.
    e. Log prep: `delta_tag.py log-prep --prospect "[NAME]" --type email_draft --prep 2`

**Step 13: Auto-prep demos** — Check Calendar sync results for demos/calls within 48 hours. For each:
    a. Check if cheat sheet exists in docs/Demo Prep/ or brain/demos/
    b. If NO cheat sheet: auto-build from prospect file + LinkedIn + NotebookLM + Fireflies
    c. If cheat sheet EXISTS: surface it with any updates needed
    d. Log prep: `delta_tag.py log-prep --prospect "[NAME]" --type cheat_sheet --prep 3`
    e. Present prep to Oliver. Don't skip.

**Step 14: Surface findings:**
```
SYNC: [N]/5 sources fresh | [api_sync status]
  Pipedrive: [N] deals ($X) | [N] stage changes
  Gmail: [N] sent, [N] replies | Calendar: [N] meetings 7d
  Instantly: [N] replies ([rate]%) | Fireflies: [N] recordings
  REPLIES: [who replied, sentiment]
  OVERDUE: [touches past due]
  DUE TODAY: [touches due, suggested angle from PATTERNS.md]
  UPCOMING: [next 3 days]
```
If all sources fresh and nothing overdue: keep to 3 lines.

## Phase 2: CARL (lightweight)

**PARALLEL BATCH (steps 8, 9, 10 — three independent file reads, fire all at once):**
8. **Read .carl/manifest** — check active domains.
9. **Read .carl/global** — AIOS universal rules. **Also read domain/carl/global** — domain-specific rules (research protocol, skill loading, CCQ, OOO, channel collision, credit gate).
10. **Read .carl/context** — context bracket rules. **Read .carl/safety** — structural protections.

**THEN (sequential, needs manifest loaded):**
11. **Keyword-match CARL domains against Oliver's first message** — load demo-prep or prospect-email domain only if task triggers recall keywords.

## Phase 3: Task-Triggered Loading (on demand)

Load these ONLY when the task requires them. Do not preload.

**This is intent-based routing, not literal keyword matching.** Read Oliver's message for what he's trying to DO, then load the right context. Examples below are illustrative, not exhaustive.

### Email writing (any type)
**Intent:** Oliver wants to write, draft, send, or edit any email — cold, inbound, follow-up, reply, sequence, etc.
**Load:** "domain/templates/templates.txt", domain/carl/prospect-email, "domain/playbooks/my-role.txt"
**Also load if cold outreach:** domain/sprites_context.md (for case studies/proof points)

### Demo prep (any demo)
**Intent:** Oliver wants to prepare for a demo, call, or meeting. Could reference a name, a time ("my 2pm"), "today's demos", "tomorrow's call", or a company name.
**Load:** "domain/playbooks/sales-methodology.txt", "domain/prep/Demo Threads.txt", domain/carl/demo-prep
**Then:** Check calendar to identify which demo, find/create prospect note in "docs/Demo Prep/" and Obsidian brain

### Prospecting / list building / contact finding
**Intent:** Oliver wants to find leads, build lists, research companies, enrich contacts, find employees at a company, get contact info, run sweeps, or score prospects. Triggers on: "find me", "give me a list", "get contacts", "who works at", "employees at", "[company] team", "find leads", "build a list", "prospect", "enrich", or any request to discover companies or people.
**Load:** "domain/playbooks/prospecting-instructions.txt"
**Tools -- waterfall approach (try free first, escalate to paid):**
1. **Free scripts first** (`brain/scripts/prospecting/`):
   - Company discovery: `google_maps.py` (by location), `meta_ads.py` (by ad activity), `job_boards.py` (by hiring signals)
   - Qualification: `tech_scanner.full_scan(domain)` -- ad pixels, marketing stack, DNS intel
   - Contact finding: `contact_finder.find_contacts(domain)` -- team page scraping + email patterns
   - Full pipeline: `pipeline.py --config sample_config.json`
2. **Apollo (free tier)** -- fall back here when free scraping returns no contacts. Use `apollo_contacts_search` or `apollo_mixed_people_api_search` for employee lookup.
3. **Never tell Oliver to run scripts manually.** Import Python functions and call them inline, or use Apollo MCP tools directly.

### Product knowledge / case studies
**Intent:** Oliver needs Sprites product details, pricing, ICP deep-dive, case study specifics, objection handling, or competitive positioning.
**Load:** domain/sprites_context.md
**Prefer:** Use `ctx_index` + `ctx_search` instead of reading full file when only a specific section is needed.

### Lead campaign management
**Intent:** Oliver asks about campaign status, sweep progress, batch progress, enrichment state, or lead pipeline.
**Load:** Leads/STATUS.md, check Leads/wip/

### Prospect history / notes
**Intent:** Oliver mentions a specific person or company and needs context on prior interactions.
**Load:** Check Obsidian brain (C:/Users/olive/SpritesWork/brain/prospects/), check Apollo Activities tab

### Problem-solving / debugging / stuck
**Intent:** Oliver is stuck, debugging, asks "why isn't this working", "figure out", "is this possible", "how do I", or presents a problem requiring research and iteration rather than a simple lookup.
**Load:** skills/fitfo/SKILL.md

### General rule
If the task spans multiple intents (e.g., "prep for Tim's demo and draft the follow-up for Hassan"), load context for ALL relevant intents. When in doubt about whether to load something, load it — a few extra thousand tokens is cheaper than missing context and producing bad output.

## Phase 4: Skills (on demand)

Do NOT preload all sales skills. Load the relevant subset based on what Oliver is doing:

- **Writing cold outreach** → cold-email-manifesto, copywriting
- **Preparing for demos/calls** → buyer-psychology, jolt-indecision, sales-methodology (already in Phase 3)
- **Building prospect lists** → fanatical-prospecting, outbound-playbook
- **Writing follow-ups** → jolt-indecision, buyer-psychology
- **Handling objections / indecision** → jolt-indecision

Salesably skills (skills/sales-skills/skills/) — load only the specific one relevant to the task, never all 9.

## During Session: Obsidian Brain

Use the brain proactively — don't wait to be told.

**Before any prospect work:**
- Check `C:/Users/olive/SpritesWork/brain/prospects/` for existing notes on the person/company
- If a note exists, read it before hitting Apollo or burning credits

**After any interaction** (email sent, call done, demo, research):
- Create or update the prospect note in `brain/prospects/[Name] — [Company].md`
- Use tags: `#lead`, `#demo-booked`, `#demo-done`, `#follow-up`, `#onboarding`, `#closed-won`, `#closed-lost`
- Include: contact info, company context, outreach history, objections, next steps

**Tag-based queries (on-demand, not at startup):**
- When Oliver asks about follow-ups or pending items, scan `brain/prospects/` for `#follow-up` or `#demo-booked` tags
- Do NOT bulk-scan all prospect files at startup — use startup-brief.md as the pipeline source of truth and only auto-load Tier 1 (48h-due) prospects

**Auto-sync rule:**
When you learn new info from Apollo, Fireflies, or Clay during a session, update the brain note immediately. Don't batch it for wrap-up — write it as you go so the note is always current.

## During Session: NotebookLM (see .claude/skills/notebooklm/SKILL.md for tier system)

Query proactively when the task benefits from it:
- **Demo prep:** Add prospect website to Demo Prep notebook (`6bdf40a0-e9e5-462b-bfcd-02a2985214c1`), query for marketing intel
- **Email writing:** Query Sprites Sales notebook (`1e9d15ed-0308-4a30-ae27-edf749dc8953`) for relevant case studies
- Don't wait to be told. If the task involves a prospect, NotebookLM adds value.

## Session End: Update domain/pipeline/startup-brief.md + Brain

During wrap-up, update domain/pipeline/startup-brief.md with:
- Pipeline changes (new prospects, demos booked, deals closed)
- Campaign progress
- New top lessons
- Credit balance changes

Also write a session summary to `C:/Users/olive/SpritesWork/brain/sessions/[YYYY-MM-DD] — [Session Type].md`

This keeps the next session cheap and current.

## Self-Heal Protocol

Auto-fix infrastructure handles most failures. Manual escalation only when auto-fix exhausts retries.

### Automatic Self-Heal (runs without Oliver)
1. **Validator retry loop** — wrap_up_validator.py runs 15 binary checks (80% threshold). On FAIL, auto-fix attempts up to 3 cycles before escalating. Covers: file existence, header consistency, event logging, git state, bloat limits.
2. **Startup self-heal** — session_start_reminder.py hook runs 6 automated checks (vault, DB, PATTERNS, git, CLAUDE.md lines, events.jsonl). Auto-creates events.jsonl if missing. Surfaces CRITICAL/WARNING alerts.
3. **Config validator** — config-validate.js hook validates JSON configs at startup. Flags malformed configs before they cause downstream failures.
4. **Agnix** — config lint tool. Auto-runs at startup to catch structural drift in CARL/manifest/rules files.
5. **Ruff auto-fix** — Python linter runs at wrap-up. Auto-fixes formatting issues in brain/scripts/.

### Manual Escalation (only when auto-fix fails)
1. Try alternative method (different tool, python, web search)
2. Log failure via `python brain/scripts/events.py` with event_type TOOL_FAILURE
3. NEVER silently skip. Tell Oliver what failed.
4. Python: C:/Users/olive/AppData/Local/Programs/Python/Python312/python.exe (python-docx, openpyxl)
5. If ANY MCP tool call fails during Phase 1-2, follow .claude/fallback-chains.md. Only escalate to Oliver if fallback also fails.

## Output

After loading, give Oliver a concise status (plus freshness alerts if any):
```
[check] Context loaded (brief, lessons, CARL, vault) | ~XXk tokens
[morning] [Morning brief status — fresh/stale/not available]
[calendar] [Today's demos/meetings if any]
[clipboard] [Active campaign one-liner]
[vault] [Prospects needing follow-up from brain/ scan]
[signal] [Unprocessed signals with relevance >= 7 — only show if any exist]
[heartbeat] [X/4 systems healthy] [list any failures]
[health] [Deal health alerts — any deals below 40 health score]
[alert] [Files changed since last session — only show if something changed]
```

Include approximate token spend for the startup sequence (file reads + API calls + tool schemas). This helps Oliver track context budget.

Do not dump a wall of text. Confirm loaded, surface time-sensitive items, respond to Oliver's request.
