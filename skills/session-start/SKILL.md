---
name: session-start
description: Run automatically at every session start before responding to Oliver's first message. Loads domain/pipeline/startup-brief.md, lessons.md, CARL, and checks Google Calendar. Defers all other context to on-demand loading based on task intent. Use this skill whenever a new session begins, the user says "start up", "load context", or any time CLAUDE.md's session startup instructions need to execute. This is mandatory — never skip it.
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
5. **Initialize neural-bus** — create fresh brain/sessions/neural-bus.md for this session. Archive previous session's bus to brain/sessions/neural-bus-[prev-date].md. Write first signal: `[HH:MM] [session-start] [INIT] session=[N] stale_files=[list] brain_alerts=[N]`

## Phase 0.5: System Heartbeat

Quick health pulse before loading context. **Run steps 1-4 + 7 as a single parallel batch** — they are independent file checks with no dependencies between them.

**PARALLEL BATCH (all at once):**
1. Check brain/system.db exists and is readable (SQLite backing store)
2. Check brain/.git exists (version control active)
3. Check domain/carl/loop file size hasn't changed unexpectedly (rule tampering detection)
4. Check CLAUDE.md line count is under 150 (bloat detection)
7. **Gap Scanner** — run .claude/gap-scanner.md startup scan. Check all systems connected, detect process drift from canonical_logs, surface any gaps in the startup status output.
8. **Brain launch check** — run `python brain/scripts/launch.py --json`. Validates header consistency (session numbers match across loop-state + startup-brief), staleness, inter-session modifications, and RAG graduation status. Surface any issues in startup output. If `rag_graduation_ready`, prompt user to activate embedding layer.

9. **Periodic audit check** — read .claude/periodic-audits.md. Compare each audit's `last_run` session number against current session number. If any audit's trigger condition is met, queue it: startup-time audits run now (RAG freshness), session-time audits note in status output ("SDK audit due this session"), wrap-up audits fire automatically at step 7.

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

## Phase 1.5: Full Tool Scan (~15 seconds with parallel calls)

> Replaces the overnight agent. Scans ALL connected tools at session start.
> If any scan fails: auto-fix via fallback chain FIRST, then surface result.
> Oliver sees results, not problems. Only escalate if fix also fails.

Load `domain/carl/loop` rules for this phase.

**PARALLEL BATCH A (all independent — fire all at once):**
5+7. **Prospect loading (two tiers)** — Read startup-brief pipeline section. Prospects with meeting/demo/follow-up due within 48h = **Tier 1** (read full brain/prospects/ file). All others = **Tier 2** (load on demand when Oliver names them). For Tier 1, check: (a) `next_touch` dates <= today, (b) untagged touches.
9. **Check brain/signals.md** — unprocessed signals with `relevance >= 7`.
10. **Gmail scan** — search for new replies since last session. `gmail_search_messages after:[last_session_date]`.
11. **Calendar scan** — today + tomorrow + next 7 days. Surface demos, calls, meetings with times.
12. **Fireflies scan** — check for new recordings since last session.
13. **Pipedrive scan** — pull Oliver-tagged deals. Check for: (a) stage changes since last session, (b) newly closed deals (won or lost) for forecasting calibration, (c) deals with zero upcoming activities.
14. **Instantly scan** — check campaign analytics for reply rate changes, new replies, bounces.

**PARALLEL BATCH B (after batch A — fire all Gmail searches at once):**
6. **Outcome check** — for EVERY prospect with `outcome: pending`, search Gmail `from:[prospect_email] after:[last_touch_date]` in parallel. Reply found → update outcome. No reply + next_touch passed → "no-reply".

**AUTO-FIX PROTOCOL:** If any scan fails (MCP timeout, connection error), run fallback chain immediately. Log: `Auto-fixed: [tool] [error] → [fallback] → [result]`. Only escalate to Oliver if fallback also fails.

**THEN (sequential):**
8. **Surface findings as checklist summary:**
```
STARTUP: [N]/[N] scans complete ✓
  Gmail: [N] new replies | Calendar: [N] meetings today | Pipedrive: [N] deals changed
  Fireflies: [N] new recordings | Instantly: [campaign] reply rate [X]%
  Auto-fixed: [tool] → [fallback] → [result] (if any)
  REPLIES: [who replied, sentiment]
  OVERDUE: [touches past due]
  DUE TODAY: [touches due, suggested angle from PATTERNS.md]
  UPCOMING: [next 3 days]
  CLOSED DEALS: [any newly closed → logged to forecasting.md for calibration]
```
If all scans pass and nothing is overdue: keep to 3 lines. Details only expand on findings.

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

### Prospecting / list building
**Intent:** Oliver wants to find leads, build lists, research companies, enrich contacts, run sweeps, or score prospects.
**Load:** "domain/playbooks/prospecting-instructions.txt"

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

If ANY step fails:
1. Try alternative method (different tool, python, web search)
2. Log failure in .claude/lessons.md
3. NEVER silently skip. Tell Oliver what failed.
4. Python: C:/Users/olive/AppData/Local/Programs/Python/Python312/python.exe (python-docx, openpyxl)
5. If ANY MCP tool call fails during Phase 1-2 (calendar, Gmail, Apollo, etc), immediately tell Oliver: "Run /doctor in terminal — [tool name] isn't responding." Don't retry silently more than once.

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
