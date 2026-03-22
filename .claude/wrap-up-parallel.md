# Wrap-Up & Startup Parallelization Map

> Execution plan for session wrap-up and startup. Loaded by session-start skill and wrap-up process.
> Brain layer: YES (logic is portable). Runtime layer: Step 12 is Windows-specific.

---

## HOW TO USE

**Wrap-up:** Fire Wave 1 as parallel background agents. When all complete, fire Wave 2. When all complete, fire Wave 3. Step 11c runs after Wave 3 (conditional).

**Startup:** Run Phase -1 sequentially. Then fire each subsequent phase in parallel. Phase 1.5 Batch B waits for Batch A.

---

## WRAP-UP WAVES

```
Wave 1 ──────────────────────────────────────────────────────
  (fire all at once, zero dependencies)
  │
  ├─ Agent A: Step 0.5 + 1  Session note (docs/Session Notes/)
  │           Write Oliver's Summary + daily notes + self-assessment
  │           Output: docs/Session Notes/[YYYY-MM-DD]-S[N].md
  │
  ├─ Agent B: Step 2         Log lessons (IF corrections received)
  │           Output: .claude/lessons.md (append)
  │           SKIP if no corrections this session
  │
  ├─ Agent C: Step 7         /reflect + anti-bloat
  │           Decrement [PROVISIONAL:N] counters
  │           Check for 3+ similar corrections → propose rule upgrade
  │           Daily note rotation, lessons graduation
  │
  ├─ Agent D: Step 9.5       Git checkpoint
  │           Stage brain/ changes, commit 'Session [N]: [summary]'
  │           Increment patch in brain/VERSION.md
  │           Every 5th session: minor version + git tag
  │
  └─ Agent E: Step 12        Session cleanup (Windows-specific)
              Remove orphaned Claude Code project folders
              Output: count of removed vs remaining folders
```

```
Wave 2 ──────────────────────────────────────────────────────
  (needs Wave 1 complete — depends on lessons + session note)
  │
  ├─ Agent F: Step 6         Health audit
  │           Abbreviated if systems-only session
  │           Input: lessons from Wave 1, session note
  │           Output: health scores
  │
  ├─ Agent G: Step 8         Post-session audit
  │           Run auditor-system.md + loop-audit.md
  │           Score all dimensions
  │           HARD GATE: 8.0+ to close — if fail, fix-cycle
  │           Input: session note, lessons, reflect output
  │
  ├─ Agent H: Step 9         Cross-wire checklist
  │           Check all triggers (EVENT, TREND, DANGER)
  │           Log to brain/system-patterns.md
  │           Show compound brain status
  │
  └─ Agent I: Step 10        Brain session summary
              Write brain/sessions/[YYYY-MM-DD].md
              Include: narrative, corrections, outcomes, scores
              Input: session note, audit scores
```

```
Wave 3 ──────────────────────────────────────────────────────
  (needs Wave 2 complete — depends on scores + audit results)
  (all items write to different files → fire in parallel)
  │
  ├─ Agent J: Step 3         Vault sync + NotebookLM feed
  │           IF prospects/vault touched
  │           Feed new/updated brain files to matching notebooks
  │           Output: brain/ prospect files, NotebookLM updates
  │
  ├─ Agent K: Step 10.5      Startup brief refresh
  │           Update domain/pipeline/startup-brief.md
  │           Header: # Last updated: [DATE] (Session [N])
  │           Update handoff, pipeline table, system state
  │
  ├─ Agent L: Step 11        Handoff — rewrite loop-state.md
  │           Header: # Loop State — Last Updated [DATE] (Session [N] Close)
  │           Pipeline snapshot, pending, what changed, due next
  │           Loop health score. Under 80 lines.
  │           [TAG] prefixes on "What Changed" bullets
  │           >>> VERIFY header session number matches current session <<<
  │
  └─ Agent M: Step 11b       Agent distillation
              Read agents/registry.md
              Match lessons → agent scope tags
              Match vault deltas → agent scope paths
              Match [TAG] bullets → agent scope tags
              Write to agents/[name]/brain/updates/[YYYY-MM-DD]-S[N].md
              Skip agents with zero matches. No empty files.
```

```
Post-Wave 3 (sequential, conditional) ──────────────────────
  │
  └─ Step 11c: Self-audit check
               IF session number % 10 == 0 → output reminder
               ELSE skip silently
```

### Dependency Graph

```
Wave 1:  [0.5+1] [2] [7] [9.5] [12]     ← all independent
            │      │   │
            ▼      ▼   ▼
Wave 2:  [6] [8] [9] [10]                 ← need session note + lessons + reflect
            │   │   │
            ▼   ▼   ▼
Wave 3:  [3] [10.5] [11] [11b]           ← need scores + audit results
                       │
                       ▼
Post:              [11c]                   ← needs handoff written
```

### Conditional Steps

| Step | Condition | If false |
|------|-----------|----------|
| 2 | Corrections received this session | Skip entirely |
| 3 | Prospects/vault touched | Skip entirely |
| 4 | Interactions happened (Loop tactics) | Skip entirely — not in wave map, runs ad-hoc |
| 5 | Domain data touched (CRM/deals) | Skip entirely — not in wave map, runs ad-hoc |
| 6 | Systems-only session | Run abbreviated |
| 11c | Session number divisible by 10 | Skip silently |

---

## STARTUP PHASES

```
Phase -1: DELTA_SCAN (sequential) ──────────────────────────
  │
  └─ Read brain/loop-state.md
     Detect what changed since last session
     Must complete before anything else fires
```

```
Phase 0 + 0.5 (parallel) ──────────────────────────────────
  │
  ├─ Stale brief detection
  │  Check modification dates on startup-brief.md, loop-state.md
  │  Flag if older than 2 sessions
  │
  └─ System heartbeat
     brain/.git integrity
     system.db check
     CLAUDE.md line count (detect bloat)
     Gap scanner
     Brain launch check
```

```
Phase 1: Core (fire all 3 in parallel) ─────────────────────
  │
  ├─ Read domain/pipeline/startup-brief.md
  │  Pipeline state, deal health, handoff items
  │
  ├─ Read .claude/lessons.md
  │  Last 3 entries in brain/metrics/
  │  Note correction patterns to avoid
  │
  └─ Check Google Calendar
     Today + tomorrow + 7 days out
     Surface meetings, demos, deadlines
```

```
Phase 1.5: Full Tool Scan ──────────────────────────────────

  Batch A (fire ALL in parallel):
  │
  ├─ Prospect loading (Tier 1 only)
  ├─ Check brain/signals.md
  ├─ Gmail scan
  ├─ Calendar scan (extended)
  ├─ Fireflies scan
  ├─ Pipedrive scan
  ├─ Instantly scan
  │  list_campaigns → get_campaign_analytics → compare to PATTERNS.md
  │
  └─ Follow-up drafting trigger
     Read Follow-Up Tracker, draft due emails

  ── Batch A complete ──

  Batch B (depends on Batch A):
  │
  └─ Gmail outcome checks
     Cross-reference replies against logged outreach
```

```
Phase 2: CARL (fire all 3 in parallel) ─────────────────────
  │
  ├─ Read .carl/manifest
  │
  ├─ Read .carl/global + domain/carl/global
  │
  └─ Read .carl/context + .carl/safety
```

### Startup Dependency Graph

```
Phase -1:  [DELTA_SCAN]                    ← sequential, first
               │
               ▼
Phase 0:   [Stale Brief] [Heartbeat]       ← parallel
               │
               ▼
Phase 1:   [Brief] [Lessons] [Calendar]    ← parallel
               │
               ▼
Phase 1.5: [Batch A: 8 scans in parallel]
               │
               ▼
           [Batch B: Gmail outcomes]
               │
               ▼
Phase 2:   [CARL x3 in parallel]
               │
               ▼
           STATUS OUTPUT (3-line + Loop health + deal alerts)
```

---

## AGENT ASSIGNMENT NOTES

- Each Wave 1-3 agent receives: session number, date, session context summary
- Agents writing to brain/ should use `isolation: "worktree"` if overlapping paths are possible
- Step 8 agent (post-session audit) owns the 8.0+ gate — if it fails, it fix-cycles before returning
- Step 11 agent MUST verify header session number after writing — self-check before returning
- Startup agents are read-heavy — no worktree needed, parallel reads are safe
- Phase 1.5 agents hit external APIs — fire all at once, collect results as they return
