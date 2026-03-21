---
name: wrap-up
description: Use when user says "wrap up", "close session", "end session",
  "wrap things up", "close out", or invokes /wrap-up — runs
  end-of-session checklist for sales ops, memory, and self-improvement
---

# Session Wrap-Up

## Phase 0: Calculate Session Weight (ALWAYS_ON — runs first)

Calculate weight score before any other wrap-up step. This determines depth for all subsequent phases.

**Scoring:**
- +1 per 5 files changed this session
- +2 per CARL domain modified (AIOS or domain/)
- +3 per structural change (file move/delete/new domain/new directory)
- +1 per new lesson added
- +1 per prospect interaction (email, call, demo, research)
- +5 automatic if any core file modified (CLAUDE.md, session-start, wrap-up, .carl/manifest)

**Weight Tiers:**

| Tier | Score | Depth | Target Time |
|------|-------|-------|-------------|
| 1 — Light | 1-3 | Skip unchanged sections. Compress health check to 30s. One-line status per area. Fast commit, no scoring. | < 2 min |
| 2 — Medium | 4-7 | Run health check on changed areas only. Skip unchanged CARL domains and skills. Standard quality scoring. | < 5 min |
| 3 — Heavy | 8-12 | Full integration audit across all layers. Heal broken connections. Verify compounding chain. Full quality scoring. | < 10 min |
| 4 — Structural | Any session with AIOS/domain/CARL structural changes | Full Phase 1-5 integration heal regardless of score. Verify every layer connects. Mandatory smoke test on session-start and wrap-up flows. | Complete, not fast |

Session weight tier also feeds into .claude/auditor-system.md Session Weight (FULL/STANDARD/COMPRESSED/ABBREVIATED) — these are complementary: this tier controls wrap-up depth, auditor-system.md tiers control audit depth. Both auto-select based on session output.

**Output:** `SESSION WEIGHT: [score] → Tier [N] ([Light/Medium/Heavy/Structural])`

Then proceed to Phase 1 at the depth determined by the tier.

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
7. Check if any Apollo contact records need updating (stage changes, notes, tags)
8. Flag any contacts discussed this session that are missing from Apollo

**Task cleanup:**
8. Check the todo list for in-progress or stale items
9. Mark completed tasks as done, flag orphaned ones
10. Surface any promised follow-ups that haven't been sent

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

## Phase 4: Anti-Bloat Sweep

Run EVERY wrap-up. This prevents memory rot and token waste. Auto-fix without asking.

**4a. Daily note rotation:**
- If today's date ≠ the current daily note's date, start a fresh `YYYY-MM-DD.md`
- Carry forward ONLY pending items from yesterday. Everything else stays in yesterday's file.
- Yesterday's daily note should NOT be appended to again.

**4b. Lessons graduation (every 5 sessions, aligned with quality loop):**
- Scan `.claude/lessons.md` for entries that are now baked into a skill, CARL domain, or CLAUDE.md rule
- If the lesson is redundant (the fix is already enforced by the system), move it to `.claude/lessons-archive.md`
- Only keep unresolved/active lessons in the main file
- Target: lessons.md stays under 30 active entries

**4c. Prospect staleness:**
- Scan `brain/prospects/` for notes with no updates in 14+ days → add `#stale` tag
- Any prospect tagged `#stale` for 30+ days → move to `brain/archive/`
- Update domain/pipeline/startup-brief.md pipeline section to remove archived prospects

**4d. File line caps (enforce hard limits):**
- `domain/pipeline/startup-brief.md` > 60 lines → trim completed campaigns, archived prospects, old handoff details
- `CLAUDE.md` > 150 lines → archive old sections to `.claude/CLAUDE-archive.md` (protect: Rules Index, ICP, Writing Rules, Email Frameworks, Tool Stack)
- `lessons.md` > 30 active entries → force graduation check (4b)
- Daily note > 100 lines → you're logging too much detail. Summarize, don't transcribe.

**4e. Startup-brief freshness:**
- Remove any prospect from pipeline section that moved to brain/archive/
- Update credit balances if enrichment happened this session
- Update quality loop counter

Report: "Anti-bloat: [X files trimmed, Y lessons graduated, Z prospects marked stale]" or "Anti-bloat: clean, no action needed."

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

**Smoke test (always run, 5 seconds):**
- [ ] Can read: CLAUDE.md, domain/pipeline/startup-brief.md, lessons.md (file system OK)
- [ ] settings.json parses as valid JSON (config not corrupted)
- [ ] .claude.json parses as valid JSON (MCP config intact)
- [ ] brain/ directory accessible at C:/Users/olive/SpritesWork/
- [ ] .carl/manifest accessible
- [ ] Line counts: CLAUDE.md < 150, domain/pipeline/startup-brief.md < 60, lessons.md < 30 active

If any smoke test fails, fix it BEFORE writing the handoff.

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

## Phase 5b: Daily Note + Brain

**Daily note** (Sprites Work folder):
- Path: C:\Users\olive\OneDrive\Desktop\Sprites Work\[YYYY-MM-DD].md
- Append if file already exists
- Include: what we worked on, decisions made, pending items, next steps
- Keep it scannable — bullets, not paragraphs

**Brain session summary** (Obsidian vault):
- Path: C:/Users/olive/SpritesWork/brain/sessions/[YYYY-MM-DD] — [Session Type].md
- Tag with `#session` and relevant tags (`#system-improvements`, `#prospecting`, `#demo-prep`, etc.)
- Include: what we did, new rules added, gaps found, system health

**Brain pipeline snapshot** (weekly or when pipeline changes):
- Path: C:/Users/olive/SpritesWork/brain/pipeline/[YYYY-MM-DD] — Pipeline Snapshot.md
- Table of all active deals with stage, next step, priority
- Campaign status, credit balances, key observations

**Brain prospect notes** (if any prospects were touched this session):
- Create or update notes in `brain/prospects/[Name] — [Company].md`
- Don't defer this to "later" — write it now while context is fresh

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
