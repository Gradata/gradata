# CLAUDE.md Changelog
# Every rule change gets logged here with date, what changed, and why.
# If a change makes things worse, roll back by reversing the entry.

## 2026-03-21 — Genus OS Tranche 1: Governance Foundation (Session 21)
- **Source:** Audited github.com/Ironsail-llc/genus-os. Adapted governance patterns, not architecture.
- **Agent Manifest Schema:** agents/manifest-schema.md — second universal standard alongside Score. Structured markdown (not YAML). Required fields: id, name, status, version, department, description, instruction_file. Permission fields: tools_allowed, tools_denied, write_paths. Trust fields: trust_level, correction_rate, consecutive_rejections, auto_pause_threshold.
- **Agent Manifests:** Created agents/sales/manifest.md and agents/systems/manifest.md. Updated agents/registry.md to point to manifests.
- **Graduated Trust:** Trust Scores table added to brain/system-patterns.md. Per-agent correction rate tracking over 5-session rolling window. Trust levels: config-only → config+instructions → config+instructions+code. Promotion at <0.10 correction rate (Oliver approval). Demotion at >0.25 or 3 consecutive rejections (automatic).
- **Auto-Pause:** 3 consecutive rejections = SYSTEM_PAUSE signal. Circuit breaker.
- **Escalation Ladder:** Added to .claude/fallback-chains.md. 3 errors=CHANGE_STRATEGY, 4=REDUCE_SCOPE, 5=STOP. Hard abort at 10 total. CW-12 auto-generates lessons from REDUCE_SCOPE/STOP.
- **5-Point Verification:** Consolidated 9-step verification stack → 5 steps: INPUT, GOAL, ADVERSARIAL, VOICE, SCORE. Added GOAL check ("is this what was asked for?" — the missing question). Merged fix-before-score + metacognitive honesty + blocking gate into SCORE. Killed Layer 5 verify (duplicate of INPUT).
- **Agent Scaffold:** skills/agent-scaffold/SKILL.md — generates manifest + instructions + wiring.
- **Nervous System:** +4 bus signals (TOOL_DENIED, SYSTEM_PAUSE, ESCALATION_TRIGGERED, AGENT_CREATED). +3 cross-wires (CW-10 dormant, CW-11 active, CW-12 active). Cross-wire budget: 7→11 (1 dormant). Limit raised to 15.
- **Net complexity:** Verification steps reduced (9→5). Cross-wires increased (+4 net). New files: 4 created (manifest-schema, 2 manifests, scaffold skill). Modified files: 8 (registry, gates, action-waterfall, quality-rubrics, fallback-chains, cross-wire-checklist, component-map, neural-bus).

## 2026-03-20 — PASSIVE_PATTERN_RULE rewritten as modular 6-category compounding engine
- **What:** Replaced monolithic LOOP_RULE_60 with 6 independent sub-rules (60, 60B-60F). Each category compounds independently based on session activity.
- **LOOP_RULE_60:** PROSPECT WORK — reply rates, touch sequence, stage conversion, ghosted detection, angle underperformance, segment outperformance
- **LOOP_RULE_60B:** RULE CHANGES — rule count trend, domain distribution, conflict rate, merge success
- **LOOP_RULE_60C:** LESSONS — provisional trends, promotion rate, domain generation frequency
- **LOOP_RULE_60D:** HEALTH AUDIT — score tracking by category, consistent underscoring, MCP reliability
- **LOOP_RULE_60E:** WRAP COMPLIANCE — step skip tracking, internal vs external catch, skip pattern detection (always runs)
- **LOOP_RULE_60F:** SYSTEM CHANGES — path integrity, file reference accuracy, structural drift
- **Each writes to:** dedicated section in brain/emails/PATTERNS.md. Threshold breaches prepend "BRAIN ALERT:" for DELTA_SCAN pickup.
- **Rule count:** .carl/loop 62 → 67 (+5 sub-rules replacing 1 monolithic). Total across all domains: 150.

## 2026-03-20 — Proactive Intelligence Rules (3 new, no modifications)
- **What:** Added 3 proactive intelligence rules per Oliver's spec. No existing rules modified.
- **SKILL.md Phase -1 (DELTA_SCAN):** New phase before Phase 0 in session-start/SKILL.md. Reads loop-state.md, flags prospects overdue 2+ sessions, angles with 3+ consecutive no-replies, deals stagnant 14+ days. Outputs BRAIN ALERTs or "Brain clean."
- **LOOP_RULE_60 (PASSIVE_PATTERN_RULE):** Silent wrap-up checks. Underperforming angles (5+ attempts, <20% reply), ghosted candidates (3+ no-replies → #ghosted-candidate tag), segment outperformance (2x average). Only surfaces when thresholds breached.
- **LOOP_RULE_61 (WEEKLY_DIGEST_RULE):** Monday first-session 10-line brief: touches, reply rate trend, best/worst angle, pipeline movement, most overdue. Displays after BRAIN ALERTs, before session status.
- **Rule count:** .carl/loop 60 → 62. Total across all domains: 145.
- **Conflict check:** No conflicts with existing rules. DELTA_SCAN complements Phase 1.5 (different signals). Rule 60 consumes Rule 8 output. Rule 61 is sales performance vs Rule 27 system trends.

## 2026-03-19 — CARL Compaction: 187 → 114 behavioral rules
- **What:** Dedicated compaction session per LOOP_RULE_53 (was 73). All changes Oliver-approved.
- **Retirements (24 rules):** 12 global rules duplicating Claude Code defaults or CLAUDE.md sections. 6 meta-description rules (routing info in manifest). LOOP_RULE_0 (meta), R18 (interaction phrases), R63 (gap scanner overlaps R43+R44), R68 (ceiling pruning overlaps R38+R53). PROSPECTEMAIL R6 (circular CLAUDE.md ref), R9 (signature duplicate).
- **Merges (55 → 16 rules):** Loop bloat prevention 6→2, meta-loop 5→2, convergence 5→2, predictive 3→1, playbooks 3→1, signals 3→1. Agents types 5→1, contracts 2→1, pipelines 3→1, cost 2→1. Context brackets 16→3.
- **Moved to reference (12 rules):** Demo-prep deck format rules R5-R16 → docs/Demo Prep/deck-template.md. Content preserved, no longer CARL rules.
- **Files rewritten:** .carl/global, loop, agents, context, coldcall, demo-prep, linkedin, listbuild, prospect-email (all 9 behavioral domains)
- **Files created:** docs/Demo Prep/deck-template.md
- **Files deleted:** None (sequence-engine already deleted prior session)
- **Rule number mapping:** All domains renumbered sequentially from 0. Cross-references updated in merged rules (e.g., cross-wire rules now reference R28-R34 not R34-R40).
- **Note:** Original count was 187 (not 166 — B/C/D suffix rules were missed by grep). True reduction: 187→114 = -73 rules. Remaining 14 over ceiling. Flag per Oliver: Claude Code is runtime dependency for the 12 retired global defaults.

## 2026-03-19 — System Reflection + Vault Decay + Micro-Reflections
- **What:** Full system reflection pass, then 6 new CARL rules + 5 fixes.
- **LOOP_RULE_74-76:** Vault decay — prospect notes >90d without active deal archived, persona patterns decay confidence every 60d, objections >120d without recurrence flagged [STALE].
- **LOOP_RULE_77:** Lesson archive compaction — every 30 sessions, graduated lessons whose CARL rule has been stable 30+ sessions move to lessons-archive-retired.md (cold storage).
- **LOOP_RULE_78:** Weekly vault health metric — count prospect/persona/objection/competitor entries, flag >20% WoW growth or empty categories.
- **LOOP_RULE_79:** Micro-reflection trigger — 60-second integration check before every system addition. Checks conflicts, redundancies, unlocks. Logged to .claude/micro-reflections.md.
- **Fix:** LOOP_RULE_71 numbering corrected (was placed after 73, now between 70 and 72).
- **Fix:** Demo Prep gate step 6 (Fireflies) clarified — pre-demo searches for PRIOR calls only, not current demo.
- **Fix:** Deleted deprecated .carl/sequence-engine (replaced by .carl/loop in Session 3).
- **Fix:** system-evolution.md rule count corrected from "~70" to actual 225 (166 behavioral).
- **Fix:** system-patterns.md complexity budget corrected from "~66" to actual 166 (OVER CEILING).
- **Created:** .claude/micro-reflections.md (log file for LOOP_RULE_79).
- **Net rules:** +6 added (R74-79), 0 removed. Total CARL: 225 (166 behavioral).
- **Reflection findings:** CARL rules at 166% of ceiling, lessons.md at 117% of cap, PROVISIONAL counters never decremented, 5 cross-wires never fired. CARL compaction review needed per LOOP_RULE_73.

## 2026-03-18 — Enterprise Recursive Self-Improvement Architecture
- **What:** Full 5-layer recursive optimization system + 6 enterprise capabilities deployed.
- **Layer 3:** Cross-wiring rules (LOOP_RULE_34-40) — 7 bidirectional component connections. Auditor→gates, gates→lessons, lessons→CARL, smoke→lessons, rubric drift→tighten, fallback→reorder, PATTERNS→gates.
- **Layer 4:** Meta-loop (LOOP_RULE_41-45) — tracks which cross-wires produce value. Kill dead wires, strengthen high-value ones. Runs every 5 sessions.
- **Layer 5:** Convergence + kill switches (LOOP_RULE_46-50) — 5 maturity indicators, auto-disable after 5 cycles of zero value, complexity budget caps, divergence detection.
- **Predictive Pipeline:** LOOP_RULE_51-53 + brain/forecasting.md — deal health scoring (0-100), close probability model, revenue forecasting. Calibrates at 15+ closed deals.
- **Self-Evolving Playbooks:** LOOP_RULE_54-56 — frameworks auto-promote per persona, dead playbooks archived.
- **Signal Monitoring:** LOOP_RULE_57-59 + brain/signals.md — 5 signal types, relevance scoring, source tracking.
- **Overnight Agent:** Scheduled task 7am PT weekdays. Gmail/Fireflies/Pipedrive/Instantly scan, pre-drafts, morning-brief.md.
- **Multi-Agent Architecture:** .carl/agents domain — Research/Draft/CRM/Audit agent specs with handoff protocols.
- **Files created:** brain/forecasting.md, brain/signals.md, .carl/agents, skills/overnight-agent/SKILL.md, scheduled-tasks/overnight-agent
- **Files modified:** CLAUDE.md, .carl/loop (+26 rules), .carl/manifest, brain/system-patterns.md, skills/session-start/SKILL.md
- **Why:** Oliver's vision — transform from reactive (human→AI tracks) to anticipatory (AI predicts→prepares→executes safe→escalates judgment). Recursive self-improvement with natural convergence and kill switches preventing infinite complexity.
- **Impact:** System now has 59 CARL loop rules, 7 cross-wire connections, 5 convergence indicators, overnight pre-session automation, and math-based pipeline forecasting framework.

## 2026-03-18 — Audit Hard Gate (8.0 minimum)
- **What:** Session wrap-up now requires combined audit score of 8.0+ before closing. If below 8, fix and re-score until it passes.
- **Why:** Oliver wants quality enforced at wrap, not deferred to next session.
- **Files updated:** CLAUDE.md (wrap-up step 8), auditor-system.md (hard gate section), loop-audit.md (scoring thresholds)
- **Impact:** No session closes with known gaps. Fix-before-wrap replaces fix-next-session.

## 2026-03-18 — Bloat Prevention + Audit Fixes
- **What:** Added LOOP_RULE_25-30 (bloat prevention). Fixed loop-state.md (duplicate Gmail entries, cleaner format). Research backfill for 3 prospects via Apollo.
- **Why:** Audit score was 6.5/10 due to research-empty prospects and no file size limits. System could grow unbounded.
- **Rules added:** State file max 80 lines. PATTERNS.md max 300 lines. Prospect notes max 150 lines. 20 active prospect limit. 7-day session note retention. Startup token budget defined.
- **Research:** Celia Young (ICP 4), Olivia Gomez (ICP 3), Jennifer Liginski (ICP 9 — core match)
- **Impact:** Audit score 6.5 → 8.0/10. System now self-limits growth.

## 2026-03-18 — Loop State File
- **What:** Added brain/loop-state.md as session checkpoint. Updated CLAUDE.md startup to read state file first.
- **Why:** Every session was re-reading 10+ files (~800 lines) to figure out what's due. State file = 50 lines.
- **Impact:** ~750 lines saved per startup. Wrap-up now rewrites state file as handoff.

## 2026-03-18 — Loop System Launch
- **What:** Replaced "Sequence Engine" with "Loop" — universal closed-loop sales intelligence
- **Why:** Sequence Engine only covered emails. Loop covers ALL sales activities (emails, calls, demos, proposals, closes) with two-tier data (Cold from Instantly, Pipeline from Claude-written)
- **Files created:** skills/loop/SKILL.md, .carl/loop, .claude/loop-audit.md
- **Files updated:** CLAUDE.md, .carl/manifest, brain/emails/PATTERNS.md
- **Files deprecated:** skills/sequence-engine/SKILL.md, .carl/sequence-engine
- **Data seeded:** 82K+ emails from Instantly campaigns (Anna's + Oliver's) harvested into PATTERNS.md
- **Impact:** Loop is ALWAYS_ON, informs every session, and includes its own auditor

## 2026-03-18 (Initial Enterprise Buildout)

### Added
- Pipedrive Pipeline Check (session startup)
- Gmail Reply Check (session startup)
- Fireflies New Recording Check (session startup)
- Post-Call Debrief Trigger (session startup)
- Obsidian vault as step 0 in Prospect Research Order
- Obsidian vault as step 0 in Pre-Draft Research Gate
- Obsidian vault as step 0 in Demo Prep Research Gate
- Pre-Draft Research Gate (7-step mandatory checklist)
- Pre-Draft Checkpoint (approval before drafting)
- Email Structure (4-part locked format)
- Demo Prep Research Gate (8-step mandatory checklist)
- Story-Trap Demo Structure (TRAP sections per thread)
- Post-Demo Follow-Up Gate (Fireflies mandatory)
- Cold Call Script Gate (LinkedIn mandatory)
- LinkedIn Message Gate (profile visit mandatory)
- Pipedrive Note Quality Gate (7 rules)
- Pipedrive Note Templates (5 standardized templates)
- Pipedrive Auto-Sync Rules (6 automatic triggers)
- Calendar Check (2 months out, mandatory before tasks)
- Hands-Off Fields (deal value/pricing)
- Credit Conservation rules
- Weekly Pipeline Review (Monday ritual)
- Win/Loss Analysis Gate (mandatory on every close)
- Proactive Fireflies Check (session start)
- Self-Check rule (verify gates before presenting output)
- Subagent quality rules (templates + post-validation)
- Email tracking (wrap-up step 3.5)
- Obsidian vault sync (wrap-up step 3)
- Post-session audit (wrap-up step 7)
- Parallel agent rule (3+ independent items)

### Changed
- Prospect Research Order: added step 0 (Pipedrive) and step 0.5 (vault)
- Wrap-up checklist: expanded from 5 to 7 steps
- Fireflies search: expanded to all team members + attendee email matching

### Files Created
- .claude/auditor-system.md
- .claude/audit-log.md
- .claude/review-queue.md
- .claude/quality-rubrics.md
- .claude/fallback-chains.md
- .claude/changelog.md
- .claude/lessons-archive.md
- brain/objections/ (2 notes)
- brain/competitors/ (2 notes)
- brain/personas/ (2 notes)
- brain/templates/ (1 note)
- brain/demos/ (1 note)
- brain/pipeline/email-tracking.md

## 2026-03-18 (Enterprise Restructure)

### CLAUDE.md Slimmed: 468 → 100 lines
- Extracted all gate checklists → .claude/gates.md (load on demand)
- Extracted all Pipedrive note templates → .claude/pipedrive-templates.md (load on demand)
- CLAUDE.md is now a routing table, not an encyclopedia
- Zero value lost — all rules preserved in reference files

### Added
- Self-score calibration system (weekly spot-check) → auditor-system.md
- Calibration drift detection → auditor-system.md
- Cross-session pattern detection → auditor-system.md
- Evidence-based lessons graduation → auditor-system.md
- Session self-assessment section in daily notes → auditor-system.md
- Weekly performance pulse template → .claude/weekly-pulse-template.md

### Files Created
- .claude/gates.md (full gate checklists, extracted from CLAUDE.md)
- .claude/pipedrive-templates.md (CRM note templates, extracted from CLAUDE.md)
