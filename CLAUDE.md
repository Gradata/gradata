# AIOS — Agent Operating System

## Domain Loading
Domain config: domain/DOMAIN.md
Load at startup after AIOS context. Domain file contains: role, ICP, tool stack, prospect loading, Pipedrive sync, email frameworks, Loop config, gate index, reference file pointers.
Domain CARL rules: domain/carl/ (loaded via .carl/manifest domain routing)
Domain gates: domain/gates/ (loaded on demand when task triggers)
Domain skills: domain/skills/ (loaded on demand)
Domain voice: domain/soul.md (Sprites email frameworks, persona, signature)
Safety rules: .carl/safety (always loaded)

## Session Startup — DO THIS FIRST
Read and execute skills/session-start/SKILL.md. Load context-manifest.md and follow its tiers. Tier 0 always loads. Tier 1 runs at startup (parallel, summarize, release). Tier 2 loads on demand. Tier 3 governed by .agentignore. Give 3-line status + Loop health line + deal health alerts, then respond.
At session start: read last 3 entries in brain/metrics/, note correction patterns, actively avoid repeating them.

## Session Wrap-Up
Save to docs/Session Notes/[YYYY-MM-DD].md. Steps 0.5, 1, 7, 8, 9, 9.5, 10, 10.5, 11 always run. Others are conditional:
0.5. **User Summary** — FIRST section in the session note. Plain English, under 200 words, no jargon. Four parts: (1) what was asked for and what was done, (2) where you were confident vs guessing, (3) one thing you did well and why, (4) one thing you're not sure was good enough. See auditor-system.md for format.
1. **Daily notes** — session summary + self-assessment (best/weakest output, gates skipped, self-scores)
2. **Lessons** [IF corrections received] — log to .claude/lessons.md
3. **Vault sync** [IF prospects touched] — update brain/ for every prospect, objection, template, demo touched
4. **Loop sync + Outcomes** [IF interactions happened] — run `/log-outcome` for any tactic→result pairs. Update PATTERNS.md. Recalculate tables.
5. **Domain sync** [IF domain data touched] — domain-specific sync (CRM, deals, activities)
6. **Health audit** [abbreviated if systems-only session] — run .claude/health-audit.md
7. **Anti-bloat + Reflect** — run `/reflect` automatically. Daily note rotation, lessons graduation (auditor-system.md), decrement [PROVISIONAL:N] counters in lessons.md. If 3+ similar corrections exist under same category, propose a rule upgrade to CLAUDE.md.
8. **Post-session audit** — run .claude/auditor-system.md + .claude/loop-audit.md. Score all dimensions. **HARD GATE: 8.0+ to close.**
9. **System Loop** — run .claude/cross-wire-checklist.md. Show cross-wire status + compound brain status. (Layers 2-5.)
9.5. **Git checkpoint** — stage and commit brain/ changes: 'Session [N]: [summary]'. Increment patch in brain/VERSION.md. Every 5th session: minor version + git tag.
10. **Session summary** — write brain/sessions/[YYYY-MM-DD].md with session narrative, corrections processed, outcomes logged, and scores.
10.5. **Startup brief refresh** — update domain/pipeline/startup-brief.md with current state. Header MUST read `# Last updated: [DATE] (Session [N])` with the CURRENT session number. Update handoff section, pipeline table, system state, and any stale data. This is the pipeline source of truth at startup — never let it go stale.
11. **Handoff** — REWRITE brain/loop-state.md. Header MUST read `# Loop State — Last Updated [DATE] (Session [N] Close)` with the CURRENT session number. Pipeline snapshot, pending items, what changed, due next session, Loop health score. Under 80 lines. **"What Changed" bullets MUST be prefixed with `[TAG]`** where TAG is a scope tag (OUTREACH, COMMUNICATION, DEMO, PIPELINE, CRM, PROSPECT, PERSONA, OBJECTION, SYSTEM, ARCHITECTURE, INTEGRATION, SAFETY, AUDIT, QUALITY, NERVOUS-SYSTEM). Bullets that match no tag are written without a prefix. **VERIFY immediately after writing loop-state.md:** confirm header session number matches the current session — if it doesn't, fix it before proceeding to 11b.
11b. **Agent Distillation** — runs after step 11 is written and verified. Read agents/registry.md (if missing, create with placeholder structure). For each ACTIVE agent: (1) collect session lessons from step 2 — match lesson category prefix against agent scope tags; (2) collect vault deltas — match changed file paths against agent scope paths; (3) collect "What Changed" bullets — match `[TAG]` prefix against agent scope tags. Write matches to `agents/[agent-name]/brain/updates/[YYYY-MM-DD]-S[N].md`. Skip agents with zero matches. No empty files.

## Work Style Rules
* Research before asking. Check available tools, calendar, vault first.
* Save to project working directory. Drafts as HTML. Hyperlink product URLs.
* SELF-CHECK before output: (1) gate complete? (2) self-score (.claude/quality-rubrics.md) — below 7 = revise. (3) fallback chain followed? Show score inline: `Score: X/10 (type) — agree? Say "that's a [X]" to override`
* **ACTION WATERFALL** — EVERY output flows through 5 layers: Context (load rules+lessons) → Memory (vault+KG+NotebookLM+patterns) → Execute → Quality (humanizer+score) → Verify (pre-flight+truth+log). See .claude/action-waterfall.md. No output bypasses the pipeline.
* Tool fails → .claude/fallback-chains.md. Domain-specific overrides in domain/pipeline/fallback-overrides.md. Never improvise. Never silently skip.
* **Never skip steps. Ever.** When told to "wrap up" — run ALL steps. When a gate has 7 steps — run all 7. No shortcuts, no judgment calls about what's optional.
* Subagents get: note template, quality rules, post-validation.
* 3+ independent items → parallel agents. Use `isolation: "worktree"` when agents may edit overlapping files or when running concurrent terminals — each agent gets an isolated repo copy, merges cleanly.
* User approves copy → straight to draft. No extra confirmation.
* Log to lessons, vault, daily notes without asking. Changelog for CLAUDE.md edits.
* **Wikilinks** — all new brain/ files (sessions, prospects, vault updates) MUST include relevant [[wikilinks]] at time of writing. Link prospects to personas/objections, sessions to prospects touched.
* Never double-dip enrichment. Never list pending from memory — verify.
* **Post-task reflection** — after every major task, run a 30-second internal check: what went wrong, what was inefficient, what would I do differently? Log anything actionable to lessons.md silently.
* **Context hygiene** — Compact at 50% context usage, not later. Past 50% quality degrades. Use subagents for discrete subtasks to keep main context focused. Use /clear when switching to a completely different task.
* **Anti-mediocrity** — If a fix or draft is mediocre, scrap it and rebuild the elegant solution from scratch. Don't patch bad work. Two clean attempts beat four incremental patches.
* **Scoped Impact Scan** — Before modifying any system component (.claude/*, .carl/*, CLAUDE.md, agents/, gates/, skills/), open component-map.md, find the component being changed, and read ONLY its row + the rows it connects to (same group or cross-referenced). State in one line: `Impact: [component] → touches [X, Y]. No breaks.` or `Impact: [component] → touches [X]. [X] needs update because [reason].` Then proceed. Don't scan the full map — just the neighborhood. Skip for brain/ data writes (prospects, sessions, notes) — those are data, not system.

## Recursive Self-Improvement (5 Layers)
- **L1 Loop** — Tag → track → learn → improve (domain activities). **L2 System Loop** — Track component effectiveness (gates, lessons, smoke checks, audits). Tracking: brain/system-patterns.md.
- **L3 Cross-Wiring** — Three trigger classes: EVENT (12 this-session triggers), TREND (4 cross-session integral/derivative), DANGER (4 anomaly signals). Utility-scored. Components feed bidirectionally: Auditor→gates, gates→lessons, lessons→CARL, smoke→lessons, rubric drift→tighten, fallback→reorder, PATTERNS→gates. Trends catch drift across sessions. Danger signals catch stress mid-session.
- **L4 Meta-Loop** — Track which cross-wire connections produce value. Kill dead wires, strengthen high-value ones. Runs every 5 sessions. **L5 Convergence** — Auto-detect maturity. Kill switches: 5 cycles zero value = auto-disable. Max 3 active layers.

## Enterprise Quality System
.claude/quality-rubrics.md | .claude/fallback-chains.md | .claude/auditor-system.md | .claude/health-audit.md | .claude/loop-audit.md | .claude/audit-log.md | .claude/review-queue.md | .claude/changelog.md | .claude/truth-protocol.md | .claude/cross-wire-checklist.md | brain/system-patterns.md | brain/metrics/ | brain/sessions/ | brain/system.db | brain/.git

## SDK Architecture
This system has two layers. Brain layer -- everything in brain/ -- is universal and platform agnostic. Runtime layer -- CLAUDE.md, hooks, commands -- is Claude Code specific. Every architectural decision must be classified as brain layer or runtime layer before implementation. Brain layer = SDK-portable by default. Runtime layer = flag in changelog as platform specific. Never mix the two. When in doubt, ask before building.

## Environment
This system runs on Windows. Always use Windows-compatible paths with backslashes or forward slashes where both are accepted. Never assume Unix-style commands or path separators. PowerShell is the default shell. Python is at C:/Users/olive/AppData/Local/Programs/Python/Python312/. Node is available. When writing bash commands default to PowerShell syntax.

## Truth Protocol
See GLOBAL_RULE_0 in .carl/global + .claude/truth-protocol.md. Single source — not repeated here.
