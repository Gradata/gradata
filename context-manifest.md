# Context Manifest — Lazy Loading Controller
# Cursor-inspired four-tier design. Controls what loads when.
# Referenced by CLAUDE.md startup. Reconciled with session-start skill.
# Goal: minimize startup tokens while ensuring nothing is missed.

## Tier 0: Always Load (<8k tokens)
Files that must be in active context for the entire session. Auto-loaded or read immediately.

| File | Est. Tokens | Why Always |
|------|-------------|------------|
| CLAUDE.md | ~4,000 | Auto-loaded by Claude Code. Master rules, gates list, work style, ICP. |
| soul.md | ~1,500 | Voice/writing rules needed for any prospect-facing output. |
| brain/loop-state.md | ~1,500 | Session checkpoint. What's due, who needs contact, what changed. |
| .carl/manifest | ~500 | Domain routing. Which CARL files to load and when. |
| .carl/global | ~300 | 4 universal AIOS rules (truth, honesty, complexity, conflict). |
| domain/carl/global | ~400 | Domain-specific rules (research protocol, skill loading, CCQ, OOO, channel collision, credit gate). |

**Tier 0 total: ~7,800 tokens**

## Tier 1: Startup Checks (read, summarize, release)
Files read during startup. Results surfaced in the 3-line status output. Full file content released from context after summary — only the findings persist.

| File / Action | Est. Tokens | Trigger | Output |
|---------------|-------------|---------|--------|
| brain/morning-brief.md | ~1,500 | If fresh (<4h), read and skip Gmail/Fireflies | Status lines for pipeline, replies, recordings |
| .claude/lessons.md | ~2,000 | Always — scan graduated index + active lessons | Relevant lessons held; file released |
| domain/pipeline/startup-brief.md | ~1,500 | Always — read Handoff section first | Pipeline state, credit balances, campaign status |
| Google Calendar (API) | ~500 | Always — today + tomorrow | [calendar] line in status |
| Gmail scan (API) | ~300 | Only emails in loop-state.md Gmail Check List | [replies] line in status |
| Fireflies scan (API) | ~300 | Match against active deals by attendee email | New recordings surfaced or "none" |
| brain/signals.md | ~500 | Scan for relevance >= 7 | [signal] line if hits exist |
| .carl/loop | ~3,000 | ALWAYS_ON — but rules referenced by number, not held verbatim | Loop health check output |
| .carl/context | ~200 | ALWAYS_ON — context bracket detection | Bracket mode set |
| System heartbeat | ~100 | Check brain/system.db, brain/.git, .carl/loop size, CLAUDE.md lines | [heartbeat] line |

**Tier 1 total: ~10,000 tokens read, ~2,000 retained (lessons + findings)**

## Tier 2: Task-Triggered (load only when needed)
Files loaded when Oliver's message or the current task requires them. Intent-based routing.

| File | Trigger Intent |
|------|---------------|
| soul.md (Writing Quality Standards) | Drafting any prospect-facing copy (email, LinkedIn, call script) — quality scoring + anti-pattern checks |
| .carl/prospect-email | Writing any email to a prospect |
| .carl/demo-prep | Preparing for a demo, call, or meeting |
| .carl/coldcall | Phone prospecting, call scripts, voicemail |
| .carl/linkedin | LinkedIn outreach, DMs, connection requests |
| .carl/listbuild | List building, CSV, enrichment, Apify, Prospeo |
| .carl/agents | Parallel work, specialized subagent tasks |
| .claude/gates.md | Running any mandatory gate (pre-draft, demo prep, etc.) |
| .claude/quality-rubrics.md | Scoring any output |
| .claude/fallback-chains.md | When a tool fails |
| .claude/truth-protocol.md | Referenced inline (rules in CLAUDE.md); full file on demand |
| .claude/auditor-system.md | Wrap-up audit |
| .claude/loop-audit.md | Wrap-up audit (Loop dimensions) |
| .claude/cross-wire-checklist.md | Wrap-up step 9 |
| .claude/health-audit.md | Wrap-up step 6 |
| domain/pipeline/pipedrive-templates.md | Publishing CRM notes |
| domain/pipeline/weekly-pulse-template.md | Monday sessions |
| domain/sprites_context.md | Product knowledge, case studies, competitive positioning |
| "docs/Sales Playbooks/sales-methodology.txt" | Demo prep, discovery calls |
| "docs/Sales Playbooks/prospecting-instructions.txt" | List building, ICP scoring |
| "docs/Sales Playbooks/my-role.txt" | Email writing context |
| "docs/Email Templates/templates.txt" | Email writing |
| "docs/Demo Prep/Demo Threads.txt" | Demo prep |
| "docs/Demo Prep/deck-template.md" | Building presentation decks |
| brain/prospects/[Name].md | **Tier 1 auto-load** if meeting/demo/follow-up due within 48h (per startup-brief.md). **Tier 2 on-demand** for all others — load when Oliver names them. Never bulk-read all prospect files at startup. |
| brain/personas/[type].md | Persona-level research |
| brain/emails/PATTERNS.md | Drafting any outbound (Loop pre-action) |
| brain/forecasting.md | Deal health updates |
| .claude/lessons-archive.md | Research gate step 0.5 (search by category) |
| .claude/review-queue.md | Checking for pending approvals |
| Leads/STATUS.md | Campaign management |

## Tier 3: Never Load (.agentignore)
Files excluded from agent context entirely. See .agentignore for patterns.

| Pattern | Reason |
|---------|--------|
| brain/archive/* | Archived prospects — restored on demand only |
| lessons-archive-retired.md | Cold storage, excluded from all search paths |
| Session Notes older than 7 days | Captured in loop-state and lessons already |
| .claude/system-evolution.md | Historical reference, not operational |
| brain/.git/* | Git internals |
| OS artifacts | .DS_Store, Thumbs.db, desktop.ini |

---

## Reconciliation: Old Startup → New Tiers

| Old Startup Step | Old Location | New Tier | Change |
|-----------------|-------------|----------|--------|
| CLAUDE.md | Auto-loaded | Tier 0 | No change |
| Loop State (step 1) | CLAUDE.md startup | Tier 0 | Promoted — always needed |
| Morning Brief (step 0) | CLAUDE.md startup | Tier 1 | Read, summarize, release |
| Gmail scan (step 2) | CLAUDE.md startup | Tier 1 | API call, result in status |
| Fireflies scan (step 3) | CLAUDE.md startup | Tier 1 | API call, result in status |
| Calendar (step 4) | CLAUDE.md startup | Tier 1 | API call, result in status |
| CARL manifest+global (step 5) | CLAUDE.md startup | Tier 0 | Promoted — always needed |
| CARL loop | session-start Phase 2 | Tier 1 | Read at startup, rules by number |
| CARL context | session-start Phase 2 | Tier 1 | Bracket detection only |
| Pipedrive (step 6) | CLAUDE.md startup | Tier 1 | Only if loop-state stale |
| Signals (step 7) | CLAUDE.md startup | Tier 1 | Scan, surface hits |
| Health check | CLAUDE.md startup | Tier 1 | Quick pulse, release |
| lessons.md | session-start Phase 1 | Tier 1 | Scan, hold relevant, release file |
| domain/pipeline/startup-brief.md | session-start Phase 1 | Tier 1 | Read handoff, release file |
| All CARL task domains | session-start Phase 2-3 | Tier 2 | No change — already on-demand |
| All gate/quality files | session-start Phase 3 | Tier 2 | No change — already on-demand |
| All sales playbooks | session-start Phase 3 | Tier 2 | No change — already on-demand |
| All prospect notes | session-start Phase 3 | Tier 2 | No change — already on-demand |

**Zero double-loads confirmed.** Every file appears in exactly one tier. The session-start skill's Phase 1/2/3 maps cleanly to Tier 1/1/2. CLAUDE.md and soul.md are the only Tier 0 reads beyond loop-state.

**Estimated startup token savings:** Old startup read ~18k tokens (CLAUDE.md 4k + lessons 2k + brief 1.5k + CARL 4k + APIs 1k + morning brief 1.5k + other reads 4k). New Tier 0 reads ~8k. Tier 1 reads ~10k but releases ~8k after summary. Net context retained at session start: ~10k (down from ~18k held). Savings: ~8k tokens of context freed for actual work.
