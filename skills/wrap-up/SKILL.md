---
name: wrap-up
description: Use when user says "wrap up", "close session", "end session",
  "wrap things up", "close out", or invokes /wrap-up — runs
  end-of-session checklist for sales ops, memory, and self-improvement
---

# Session Wrap-Up

## Pre-Phase: Metacognitive Scan (always runs, max 60 seconds)

Before classifying session type, run a quick metacognitive scan:
1. Query events.jsonl for this session's events — what types fired? (corrections, gate results, calibration)
2. Read brain/system-patterns.md — is this session better or worse than the baseline trend?
3. Ask: what is the single most important thing this session revealed about how AIOS operates?
4. Emit insight to events.jsonl via `events.emit("HEALTH_CHECK", "metacog", {"insight": "..."})`
5. If the insight implies a rule change — queue it for Phase 3 (Review & Apply) rather than acting immediately

## Phase 0: Session Type Classification (ALWAYS_ON — runs first)

Classify session as `full` (prospect work) or `systems` (architecture/infrastructure only).
This determines which of the 15 gate checks apply at wrap-up close (checks 12-15 skip for systems).

**Output:** `SESSION TYPE: [full|systems]`

Then proceed to Phase 1.

## Phase 1: Ship It

**Drafts and emails:**
1. Check Gmail drafts created this session — list any unsent drafts with recipient and subject
2. Flag any drafts that were approved but not yet sent

**File placement check:**
3. If any files were created or saved during this session:
   - Verify they are in the correct Sprites Work subfolder per CLAUDE.md folder structure
   - Auto-move misplaced files (e.g., CSVs saved to Downloads instead of Leads/)
   - Rename files to match naming conventions if violated
4. If any demo prep docs were created, verify they are in "docs/Demo Prep/"
5. If any prospect files were created, verify they are in "docs/Demo Prep/"

**Sequence Engine sync:**
6. Tag validation audit (MANDATORY before PATTERNS.md sync):
   - For each prospect touched this session, count total touches vs touches with complete tag blocks
   - Complete = type, channel, intent, tone, angle, framework, sequence_position, outcome
   - If any touch is missing tags: STOP and flag to Oliver. Do not sync to PATTERNS.md with incomplete data
   - Bad data is worse than no data — it poisons the learning loop
7. Pending outcome resolution:
   - For EVERY prospect with outcome: pending, search Gmail from:[email] after:[last_touch_date]
   - Reply found → update outcome (positive-reply/negative-reply), reply_sentiment, outcome_date
   - No reply + next_touch passed → set outcome to "no-reply"
   - Log all changes to prospect note
8. PATTERNS.md recalculation (only after tag validation passes):
   - Extract all tagged touches from brain/prospects/
   - Recalculate Reply Rates by Angle, Tone, Persona, Sequence Position, Framework tables
   - Update confidence levels (crossing 10 → [EMERGING], crossing 25 → [PROVEN])
   - Update "What NOT to Do" if any new patterns with >80% failure rate
   - Variables with <3 data points: do NOT assign confidence level, mark as [INSUFFICIENT]
9. Demo → Fireflies link:
   - For any demo completed this session, fetch Fireflies transcript by attendee email
   - Link in Demo Notes section of prospect note

**CRM hygiene:**
10. Check if any Apollo contact records need updating (stage changes, notes, tags)
11. Flag any contacts discussed this session that are missing from Apollo

**Task cleanup:**
12. Check the todo list for in-progress or stale items
13. Mark completed tasks as done, flag orphaned ones
14. Surface any promised follow-ups that haven't been sent

## Phase 1b: Feed the Notebooks (tier system: .claude/skills/notebooklm/SKILL.md)

If ANY prospect interactions happened this session (calls, emails, research, demos), feed learnings back into NotebookLM so the notebooks compound. Save feed files to `docs/Exports/notebook-feeds/`.

**After calls/demos — always feed:**
- New objections → Objection Handling (`73f909fa-1ebc-4792-aa22-d810df2d7ca0`)
- Prospect profile + outcome → ICP Signals (`bf84ba08-214f-40ce-9d5f-a37f822d25ff`)

**If deal closed or strong buying signals:**
- Conversion pattern → Closed Won Patterns (`2eb736e0-9a78-4561-8fa0-94d4a4b2b340`)

**If new competitor intel surfaced:**
- What prospect said about competitors → Competitor Intel (`829aa5bb-9bc0-4b07-a184-dc983375612b`)

Command: `notebooklm source add "C:/Users/olive/OneDrive/Desktop/Sprites Work/docs/Exports/notebook-feeds/[filename].md" -n [notebook-id]`

This is what makes the system get smarter with every session.

## Phase 2: Remember It

Review what was learned during the session. Place knowledge in the right location:

**Memory placement guide:**
- **CLAUDE.md** — Permanent rules, writing conventions, workflow changes, tool stack updates. Keep under 150 lines.
- **lessons.md** — Mistakes made, corrections received, things Oliver had to repeat. Format: date, what happened, what to do differently.
- **domain/carl/ files** — Domain-specific rules (demo-prep, prospect-email, etc.)
- **Auto memory** — Debugging insights, patterns, project quirks Claude discovered

**Decision framework:**
- Did Oliver correct me? → lessons.md
- Is it a permanent AIOS workflow rule? → CLAUDE.md
- Is it a domain-specific workflow rule? → domain/DOMAIN.md
- Is it specific to email or demo prep? → domain/carl/ file
- Is it an AIOS infrastructure rule? → .carl/global
- Is it a pattern I discovered? → Auto memory

Note anything important in the appropriate location.

## Phase 3: Review & Apply

Analyze the conversation for self-improvement. If session was routine with nothing notable, say "Nothing to improve" and proceed to Phase 4.

**Auto-apply all actionable findings immediately.** Do not ask for approval. Apply changes, then present summary.

**Finding categories:**
- **Correction** — Things Oliver had to tell me twice or correct me on
- **Skip** — Steps I skipped that I should have followed (CARL domains, research order, skill loading)
- **Friction** — Things Oliver had to ask for explicitly that should have been automatic
- **Knowledge** — Facts about prospects, products, or preferences I didn't know but should have

**Action types:**
- **CLAUDE.md** — Edit project rules
- **lessons.md** — Log the mistake and fix
- **domain/carl/** — Update domain rules
- **Auto memory** — Save insight for future sessions
- **Skill** — Document new skill or hook spec

Present summary in two sections:

Findings (applied):

1. ✅ Correction: Assumed Kathryn was only growth lead without verifying
   → [lessons.md] Never assume team size from headcount. Verify on LinkedIn.

2. ✅ Skip: Did not load CARL domains or sales skills at session start
   → [lessons.md] Always load CARL manifest + ALWAYS_ON domains first.

3. ✅ Friction: Saved file to Downloads instead of Sprites Work folder
   → [CLAUDE.md] Already added to Work Style Rules.

---
No action needed:

4. Knowledge: Sprites now offers LinkedIn ads
   Already noted in CLAUDE.md product description.

## Phase 3b: Capture Deferred Items (MANDATORY — all session types)

Scan the conversation for items Oliver mentioned as deferred, future-session, or "do later":
- "Next session we'll..."
- "Put that on the list"
- "We'll handle that later"
- "Deferred for future..."
- Any task Oliver or the system flagged but explicitly chose not to do this session

**For each deferred item found:**
1. Emit a DEFER event:
```python
python -c "
import sys; sys.path.insert(0, 'C:/Users/olive/SpritesWork/brain/scripts')
from events import emit
emit('DEFER', 'wrap_up:phase3b', {'item': 'EXACT_WORDING', 'reason': 'WHY_DEFERRED', 'source': 'oliver|system'}, session=SESSION_NUMBER)
"
```
2. The handoff agent reads DEFER events from the DB and writes them to loop-state.md § Deferred

**Also check:** existing Deferred items in loop-state.md. If any were resolved this session, emit a DEFER_RESOLVED event so the handoff agent can clean them.

**If nothing deferred:** emit nothing. The validator passes on zero DEFER events. But if items WERE mentioned and you skip this step, the next session loses context.

## Phase 4: Anti-Bloat Sweep

Run EVERY wrap-up. Automated via `brain/scripts/anti_bloat.py`.

**Step 1: Run the sweep script:**
```bash
python C:/Users/olive/SpritesWork/brain/scripts/anti_bloat.py
```

The script checks:
- **File line caps**: CLAUDE.md (150), startup-brief.md (80)
- **Lessons count**: Active [PATTERN] + [INSTINCT] entries vs 30-cap
- **Prospect staleness**: 14+ days untouched = stale, 30+ days = archive candidate
- **Startup-brief freshness**: Flags if >3 days old

**Step 2: Act on findings:**
- Line cap exceeded → trim the file (archive old sections, remove completed items)
- Lessons over cap → graduate entries already baked into skills/CARL/CLAUDE.md to `lessons-archive.md`
- Stale prospects → confirm with Oliver before archiving (don't auto-archive active deals)
- Brief stale → refresh pipeline section with current data

**Step 3: Refresh startup-brief.md:**
- Update credit balances if enrichment happened this session
- Remove archived prospects from pipeline section

Report: "Anti-bloat: [X issues found]" or "Anti-bloat: clean, no action needed."

## Phase 5: Health Check + Smoke Test

Quick verification — only check what's relevant to this session's work.

**Core (always check):**
- [ ] All files created this session are in the correct Sprites Work subfolder
- [ ] .claude/lessons.md updated if any corrections happened
- [ ] Obsidian brain updated for any prospects touched

**Task-specific (check only if relevant):**
- [ ] Gmail drafts: any approved but unsent?
- [ ] Demo prep docs in "docs/Demo Prep/" (if demo work done)
- [ ] Lead CSVs in Leads/ (if prospecting done)
- [ ] Apollo contacts updated (if CRM work done)

**Forward-looking:**
- [ ] Tomorrow's calendar checked — any demos needing prep?
- [ ] Any promised follow-ups not yet drafted?

**Smoke test:** Handled by hooks (session-start-reminder.py runs 7 health checks + config validation, context-budget.js enforces line limits). Only manual check: verify brain/ is accessible at C:/Users/olive/SpritesWork/ if any brain writes happened this session.

**Code lint (auto-fix, always run):**
```bash
# Python — fix unused imports, f-string issues
ruff check "C:/Users/olive/SpritesWork/brain/scripts" --select F401,F541 --fix --quiet

# JS — check hooks for issues (report only, don't auto-fix hooks)
biome check "C:/Users/olive/OneDrive/Desktop/Sprites Work/.claude/hooks" --max-diagnostics=5 2>&1 | tail -3
```
Run silently. Only surface to Oliver if errors remain after auto-fix.

**Update domain/pipeline/startup-brief.md** with any pipeline, campaign, lesson, or credit changes so next session starts current.

**Write the Handoff section** in domain/pipeline/startup-brief.md (## Handoff). This prevents context rot between sessions. Include:
- Last session: what type of work was done (prospect work, system building, campaign, etc.)
- Momentum: what mode were we in, what's the current energy/direction
- What was half-done: anything incomplete that MUST be picked up
- Decisions pending Oliver: things only he can decide
- First thing next session: numbered priority list for the next session
- System changes to verify: anything new that needs testing
- Quality loop counter: current count toward next quality loop

This is the MOST IMPORTANT part of wrap-up. A bad handoff means the next session wastes 10 minutes figuring out where we left off.

Mark each relevant item. Skip irrelevant ones. Fix any failures before closing.

## Phase 5a: Delta Sync (MANDATORY — runs every session)

Ensure sales data is fresh before writing the handoff. The SessionStart hook (api_sync.py)
already syncs all 5 sources automatically. This step VERIFIES and PATCHES if needed.

1. Run `python brain/scripts/api_sync.py status` — check last sync timestamps
2. If all 5 sources synced THIS session: skip re-sync, read results from sync_state
3. If any source is stale: run `python brain/scripts/api_sync.py sync --session [N]` (direct API, no MCP)
4. Show Oliver the compact delta summary (3-5 lines). Only expand on findings.
5. If any prospect replies detected → update that prospect's brain file immediately
6. If any new Fireflies recordings → flag for next session's prep mining

Do NOT use MCP tools here — api_sync.py calls APIs directly. This is a 5-second check, not a 15-second scan.

## Phase 5b: Session Note (HARD GATE — cannot commit or close without this)

**Path:** docs/Session Notes/[YYYY-MM-DD]-S[N].md
**Gate:** The session note file MUST exist and contain ALL 9 sections below before Phase 6 (git commit) can run. No exceptions. No skipping. If a section has nothing to report, write "None" — do not omit the section.

**Template (mandatory — use this exact structure):**

```markdown
# Session [N] — [YYYY-MM-DD] ([Session Type Summary])
Tags: [2-5 topic tags]

## OLIVER'S SUMMARY

**What you asked / What I did:**
[What Oliver asked for and what was actually done. Plain English, under 200 words.]

**Where I was confident / Where I was guessing:**
[Which parts had strong evidence vs which were assumptions or untested.]

**Best work today:**
[One specific thing done well, with why it was good.]

**Not sure about:**
[One thing that might not be good enough, with why.]

## Session Type
[Type E (execution) / Type A (architecture) / Type H (hybrid). Score against matching rubric in quality-rubrics.md.]

## What Was Done
[Numbered list. Each item specific and verifiable.]

## Gates
[Which gates triggered and passed. If systems-only: "No sales gates triggered (systems-only session)."]

## Best Output
[Single best output with reasoning.]

## Weakest Output
[Single weakest output with reasoning. If nothing weak: explain why.]

## Leading Indicators
[Computed from events, not self-assessed:]
- First-draft acceptance: [X]% ([unedited]/[total] outputs)
- Correction density: [X] ([corrections]/[outputs])
- Source coverage: [X]% (gates with full sources)
- Confidence calibration: [X]% (overrides within 2 pts)

## Corrections Received
[Numbered list of corrections. If none: "None."]

## Conditional Steps
[List every conditional wrap-up step (2-6) and whether it ran or was skipped, with reason.]
- Step 2 (Lessons): [ran/skipped — reason]
- Step 3 (Vault sync): [ran/skipped — reason]
- Step 4 (Loop sync): [ran/skipped — reason]
- Step 5 (Domain sync): [ran/skipped — reason]
- Step 6 (Health audit): [ran/skipped — reason]

## Reflection Signal
- Provisional lessons written: [N]
- Lessons graduated: [N]
- Blocked outputs (score <7): [N] — [list or "none"]
- Top root cause this session: [from /reflect double-loop or "none"]
- Confidence distribution: [X HIGH / Y MEDIUM / Z LOW]
- Neural bus signals: [total count] — [dominant type: gates/reflects/blocks/patterns]
- Metacognitive insight: [one sentence from Pre-Phase scan]

## Decision Journal
[For every major decision this session (angle chosen, framework selected, rule created, architecture choice), log one line:]
- DECISION: [what] | ALTERNATIVES: [considered] | REASON: [why] | CONFIDENCE: [H/M/L] | REVISIT: [condition]
[Source: Ray Dalio (Radical Transparency). If no major decisions: "No major decisions this session."]

## Simulation Accuracy
[If Layer 2.5 simulations were run, compare predictions to outcomes:]
- SIMULATION: [predicted] → ACTUAL: [result] | DELTA: [accurate/off by N]
[If no simulations: "No simulations this session (systems-only / SIMPLE tasks)."]

## Line Counts
- CLAUDE.md: [X]/150
- lessons.md: [X] active (cap 30)
- startup-brief.md: [X]/60
```

**Session Tags (MANDATORY):** Every session note header must include a `Tags:` line with 2-5 topic tags for searchability. Examples: `Tags: pipeline, demo-prep, genus, system-audit, prospecting`. These enable quick session lookup: `grep -l 'Tags:.*demo-prep' brain/sessions/*.md`

**Verification:** Before proceeding to Phase 6, check that the session note file exists at the expected path and contains all 10 section headers (OLIVER'S SUMMARY, Session Type, What Was Done, Gates, Best Output, Weakest Output, Leading Indicators, Corrections Received, Conditional Steps, Reflection Signal, Line Counts). If any section is missing, add it before committing.

**Brain session summary** (Obsidian vault — write after session note):
- Path: C:/Users/olive/SpritesWork/brain/sessions/[YYYY-MM-DD] — [Session Type].md
- Tag with `#session` and relevant tags
- Shorter than session note — narrative + scores + key outcomes

**Brain prospect notes** (if any prospects were touched this session):
- Create or update notes in `brain/prospects/[Name] — [Company].md`
- Don't defer this to "later" — write it now while context is fresh

## Phase 5b2: Parallel Wrap-Up Agents (spawn ALL 5 concurrently)

Spawn these 5 agents in a single parallel batch. They have NO cross-dependencies and run simultaneously:

| Agent | File | Role | Writes? |
|-------|------|------|---------|
| wrapup-handoff | .claude/agents/wrapup-handoff.md | Write loop-state, session note, morning brief | Yes (state files) |
| wrapup-metrics | .claude/agents/wrapup-metrics.md | Compute raw metrics, confidence updates | No (numbers only) |
| wrapup-events-auditor | .claude/agents/wrapup-events-auditor.md | Audit event emission completeness | No (report only) |
| wrapup-pattern-scanner | .claude/agents/wrapup-pattern-scanner.md | Detect recurring patterns, propose lessons | No (proposals only) |
| wrapup-session-scorer | .claude/agents/wrapup-session-scorer.md | Compute objective 0-10 session score | No (score only) |

**After all 5 complete:**
1. **CHECK SESSION SCORE (HARD GATE).** If session-scorer returns < 9.0/10: identify weak components, fix them, re-run scorer. Repeat until 9.0+ or Oliver overrides. Session cannot close below 9.0.
2. Apply pattern-scanner's lesson proposals (if any) to lessons.md
3. Record session-scorer's composite score in session_metrics
4. **EMIT AUDIT_SCORE EVENT (MANDATORY).** Call `emit_session_score(session, score_data)` from `wrap_up.py` with the session-scorer's output. This feeds `audit_trend()` and the brain report card. Without this event, brain scores degrade silently.
   ```python
   import sys; sys.path.insert(0, 'C:/Users/olive/SpritesWork/brain/scripts')
   from wrap_up import emit_session_score
   emit_session_score(SESSION, {"combined_avg": SCORE, "session_type": TYPE, ...dimensions...})
   ```
5. Act on events-auditor's flags (if critical)
6. Use metrics agent's confidence updates for self-improvement pipeline

**Context packet for all agents:** Pass session number, session type, date, and current session's key activities.

## Phase 5c: Pre-Commit Reflection Gate (HARD GATE — blocks Phase 6)

Before git commit can run, verify ALL of these. If any fails, resolve before committing:

- [ ] **/reflect has run this session** — check .claude/micro-reflections.md for today's date entry. If no entry exists, run /reflect now (even if queue is empty — it logs the empty run).
- [ ] **All instinct confidence scores updated** — wrap_up.py update_confidence() handles this. Verify no [INSTINCT:0.60+] entries remain (should auto-promote to [PATTERN]).
- [ ] **No blocked outputs shipped without override** — check session history for any output with self-score <7. If any were presented to Oliver without his explicit "ship it anyway" override, flag it as a process violation and log to lessons.md.
- [ ] **Run session gate** — `python brain/scripts/wrap_up_validator.py --session N --date YYYY-MM-DD --session-type [full|systems]`. Auto-fix runs by default. Target: 100%. If any checks still fail after auto-fix, fix manually and re-run until clean. Commit follows AFTER validator passes.
- [ ] **Collect Growth metrics (prospect sessions only)** — Query MCP tools and write to session_metrics:
  ```python
  # 1. Reply rate from Instantly (Oliver-only campaigns)
  #    get_campaign_analytics → extract reply rate
  # 2. Deal velocity from Pipedrive (avg days in current stage for active deals)
  # 3. Pipeline value trend (total pipeline $ from active deals)
  # 4. Win rate (closed-won / total closed deals, if any closed this session)
  # Store: UPDATE session_metrics SET growth_reply_rate=?, growth_deal_velocity=?,
  #        growth_pipeline_trend=?, growth_win_rate=? WHERE session=?
  ```
  Skip for systems-only sessions. This feeds the Growth brain score.

If all pass: proceed to Phase 6.
If any fail: fix the failure, then re-check before committing.

## Phase 5d: Wrap-Up Summary (ALWAYS — show to Oliver)

After all phases complete, show Oliver a compact summary. This is the ONLY wrap-up output Oliver needs to see. All prior phases run silently.

```
WRAP-UP: [N]/[N] steps complete [✓ or ⚠]
  Gate: [X]/[Y] checks ([Z]%) — [PASS/FAIL]
  Brain: System [X]% | Quality [Y]% | Growth [Z]% | Arch [W]%
  Indicators: acceptance=[X]% | corrections=[Y] | calibration=[Z]%
  Saved: [list of files written — session note, loop-state, startup brief, brain commit]
  Learned: [N] lessons | [N] graduated | [N] corrections
  Pipeline: [N] overdue, [N] due this week, [N] newly closed
```

**If any steps were skipped or failed:**
```
WRAP-UP: [N]/[N] steps complete ⚠
  SKIPPED: Step [X] ([name]) — [reason]
  FAILED: Step [Y] ([name]) — [error] — [auto-fix attempted: Y/N]
```

**Rules:**
- All 15 steps execute. Oliver sees only this summary.
- Details only surface on skip/failure.
- Compounding line MUST reference the specific output type trend, not just a generic score.
- If this is the first session of a type in 5+ sessions, note it: "First Type E session since S14 — baseline resetting."

## Phase 6: Git Checkpoint

After all other wrap-up phases complete, commit the working directory:

```bash
cd "C:/Users/olive/OneDrive/Desktop/Sprites Work" && git add -A && git commit -m "Session wrap-up — $(date +%Y-%m-%d)"
```

This captures every file change from the session in one atomic commit. If nothing changed, git will say "nothing to commit" — that's fine, move on.

### Tier 2 — Stable Snapshots (manual, prompted)

After any session where a major structural change was confirmed working (new skill architecture, CARL overhaul, file reorganization, etc.), prompt Oliver:

> "Structural change confirmed working. Tag a stable snapshot? `git tag stable-vX.X -m "description"`"

Do NOT auto-tag. Oliver decides when to tag. Stable tags are the rollback targets for `git checkout stable-vX.X` if a future session breaks something.

### Tier 3 — Recovery Baseline (manual only)

The `recovery` branch exists as a nuclear restore point. It is NEVER auto-updated. Only promote to it manually when Oliver instructs:

```bash
git checkout recovery && git merge stable-vX.X && git checkout master
```

Do not touch the recovery branch during wrap-up, automation, or any other process. It moves only on explicit instruction.
