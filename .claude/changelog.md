# CLAUDE.md Changelog
# Every rule change gets logged here with date, what changed, and why.
# If a change makes things worse, roll back by reversing the entry.

## 2026-03-22 — Deep Audit: 3 Missing CLAUDE.md Rules + Waterfall Fix (Session 32)
- **CLAUDE.md**: Added big-picture gate ("state what it DOES, WHY, and behavior change before implementing"). Was only in memory + lesson — never in CLAUDE.md. Root cause of Oliver's repeated correction.
- **CLAUDE.md**: Added brutal honesty rule ("surface what's weak, risky, unsure on EVERY output"). Was only in .carl/global GLOBAL_RULE_1 + waterfall Layer 4.5 — skipped for system work.
- **CLAUDE.md**: Added fact-check gate ("verify key facts against source files before presenting ANY output"). Was only in .carl/global GLOBAL_RULE_0 — system work skipped it via light waterfall pipeline.
- **action-waterfall.md**: Split "System work" into routine (fast-track eligible) vs new component (DELIBERATE, FULL verify). New components now get full context loading + Layer 4.5 brutal honesty + full verification. Prevents architectural decisions from running on the lightest pipeline.
- **CLAUDE.md**: Step 10.5 expanded (full handoff rewrite mandate). Step 1 specifies exact file path. Step 9.5 requires wrap_up_validator.py CLEAR before commit.

## 2026-03-22 — FITFO + Delta Tagging + Session Counter (Session 31)
- **CLAUDE.md**: Added FITFO attitude rule ("When stuck, exhaust 4+ strategies before giving up. Test own solutions. Full protocol: skills/fitfo/SKILL.md"). +1 line.
- **CLAUDE.md**: Added delta tagging rule ("Every prospect-touching output MUST be logged via delta_tag.py"). +1 line.
- **CLAUDE.md**: Session counter updated from 27 to 31.
- **skills/fitfo/SKILL.md**: Created. Intent-triggered problem-solving protocol (triage, research passes, verify+iterate loop, failure protocol).
- **skills/session-start/SKILL.md**: Added prospecting intent trigger (Phase 3), FITFO intent trigger (Phase 3), manual activity detection (Step 17).
- **.claude/hooks/sprites-statusline.js**: v4 to v5. Added CQ to Line 3, added Line 4 (delta: reply/pipeline/deals/outcomes/tier).
- **brain/scripts/delta_tag.py**: Created. Activity + prep + outcome logging to SQLite.
- **brain/scripts/delta_report.py**: Created. Monthly delta computation vs industry benchmarks.
- **brain/scripts/backfill_tags.py**: Created. Historical data backfill from prospect files.
- **brain/scripts/prospecting/**: Created. 12 modules (4,708 lines). Free lead discovery + enrichment pipeline.
- **brain/vault/marketplace-audit-framework.md**: Created (v3). 3-layer enterprise audit gate with anti-gaming.
- **brain/scripts/evolution_scorecard.py**: Added DELTA section to scorecard output.

## 2026-03-21 — Self-Audit Baseline + Double-Loop Fix (Session 30)
- **CLAUDE.md**: Added source-verification gate (prove inputs loaded before generating). From self-audit double-loop finding: PROCESS_SKIP pattern persisted across 4 corrections despite individual fixes.
- **CLAUDE.md ACCURACY rule**: Added cross-source hypothesis framing default. From self-audit Lens 3: overconfidence when combining data sources for the first time.
- **periodic-audits.md**: Self-audit last_run updated S0→S30.
- **brain/vault/**: Created judgment-calibration.md (8 decisions, 62.5% optimal baseline) and outcome-retrospectives.md (5 insights, sparse pipeline data acknowledged).

## 2026-03-21 — Full System Audit Optimizations (Session 30)
- **Scoring consolidation (P5):** Merged 3 separate scoring systems (quality-rubrics self-score, auditor 5-dim, loop-audit 6-dim) into unified 8-dimension rubric in auditor-system.md. Core dims 1-5 (all sessions) + loop dims 6-8 (prospect-work only). Single 8.0+ gate. loop-audit.md retains startup check + deep audit only.
- **Duplicate skills (P2):** Removed 52 byte-for-byte duplicate skills from .claude/skills/ (canonical source: skills/). 9 unique skills preserved.
- **Startup-brief (P1):** System State updated S21→S30 with verified counts (brain v1.3.3, 86 skills, 21 lessons, 156 wikilinks).
- **Lessons (P3):** Decremented 15 [PROVISIONAL:5] → [PROVISIONAL:4].
- **Signatures (P4):** Resolved contradiction across soul.md + templates.txt (Siamak=cold/outbound, Oliver=follow-up).
- **Cross-wires (P6):** Archived dormant CW-10, CW-11 (depend on unbuilt Genus OS).
- **Loop exit (P8):** Added LOOP_RULE_22 — stop following up after 5 no-replies, explicit rejection, or deal closed-lost.
- **HOME.md (P7):** Fixed brain version v1.3.2→v1.3.3.

## 2026-03-21 — Behavioral Guidelines Adaptation (Session 30)
- **CLAUDE.md Work Style**: Added 4 new rules — design-first check (pre-execution elegance), replan on failure (STOP and rewrite plan mid-task), autonomous bug resolution (fix without escalating), no temporary fixes (explicit tech debt ban)
- **.carl/global GLOBAL_RULE_2**: Strengthened from "announce the plan" to "write a spec with failure modes, use as execution checklist, replan if blocked"
- **.claude/action-waterfall.md Layer 3**: Added checkpoint protocol — state what changed after each subtask, flag if replanning needed
- **.claude/quality-rubrics.md System/Architecture 9-10**: Added minimal blast radius + regression verification (behavioral diff, log checks) to top-tier criteria
- **Source**: External behavioral guidelines compared against existing system. 6 genuinely additive adaptations applied. No conflicts with existing rules.

## 2026-03-21 — Accuracy Rule + System Updates (Session 29)
- **CLAUDE.md Work Style Rules:** Added permanent ACCURACY rule (SDK-portable). "Never report unverified numbers/files/counts. Say 'unverified' explicitly. Confident fabrication is critical failure. Show raw output when in doubt." Reinforces GLOBAL_RULE_0 (truth protocol) at behavioral level. Oliver's direct instruction.
- **CLAUDE.md Step 3:** Vault sync now includes NotebookLM feeding. Always runs (moved from conditional to mandatory).
- **session-start/SKILL.md:** Step 14 (Instantly) made specific with MCP tool calls + PATTERNS.md comparison. Step 15 added: follow-up drafting trigger (reads Follow-Up Tracker, auto-drafts due emails).
- **Skills added:** playwright-skill (browser automation for prospecting), xlsx/pdf/pptx (document skills — pending agent install).

## 2026-03-21 — Self-Audit: Compounding Intelligence Review (Session 28)
- **Purpose:** The mechanism that closes the loop between logging data and developing expertise. Without this, the brain accumulates data. With this, the brain compounds judgment. This is the core differentiator for the marketplace — a renter pays for demonstrated expertise, not data volume.
- **skills/self-audit/SKILL.md:** Three-lens periodic review. Lens 1: Error pattern analysis (classify corrections by error type, detect double-loop candidates, find persistent vs eliminated error types). Lens 2: Outcome retrospective (win/loss by decision type, confidence calibration, sustain/improve split — max 5 insights). Lens 3: Judgment calibration (evaluate past decisions against brain state at time of decision, counterfactual analysis, confidence accuracy). Each lens runs independently.
- **brain/vault/outcome-retrospectives.md:** Created. Append-only dated entries. Brain layer.
- **brain/vault/judgment-calibration.md:** Created. Append-only dated entries. The trend in this file is the proof of expertise. Brain layer.
- **.claude/periodic-audits.md:** Self-audit row added. Every 10 sessions. First fire: Session 30.
- **CLAUDE.md:** Step 11c added (conditional). Checks session number divisible by 10, outputs reminder. Brain layer, SDK-portable.
- **.claude/component-map.md:** Self-Audit, Outcome Retrospectives, and Judgment Calibration added to Periodic Audits section.
- **Error taxonomy:** DATA_GAP, PATTERN_FAILURE, CONFIDENCE_ERROR, PROCESS_SKIP, COMMUNICATION_ERROR, NOVEL_SITUATION. Applied in Lens 1 and Lens 3.
- **Rules:** Never auto-edits core files. Surfaces candidates only. All promotions require Oliver's manual approval. Reports data sparsity honestly.
- **Research sources:** Klein (RPD), Ericsson (deliberate practice), Kahneman (Noise), Tetlock (superforecasting/Brier), Argyris (double-loop learning), Croskerry (cognitive error taxonomy), US Army AAR protocol, Heuer (ACH/competing hypotheses), Guo et al. (ML calibration/ECE), Anthropic (Constitutional AI self-critique).
- **Portability:** Skill file is AIOS layer. Vault output files are brain layer. Error taxonomy is brain layer. All SDK-portable.

## 2026-03-21 — Compound Brain → Compound Intelligence (CQ) Redesign
- **Problem:** Old Compound Brain was 5 binary liveness checks (is it running?). Saturated at 5/5 by Session 27 and stayed there permanently. Measured status, not growth.
- **Fix:** Replaced with CQ (Compound Intelligence) — 5 continuous dimensions (0-100 each) that track whether the system is actually getting smarter: Correction Decay, First-Draft Pass Rate, Knowledge Utilization, Lesson Hit Rate, Autonomy Trend.
- **CQ score:** Weighted composite, no cap, tracked per session with trajectory labels (accelerating/steady/plateau/dip). Dimensions feed each other — better lessons → fewer corrections → higher pass rate → compounding growth.
- **brain/system-patterns.md:** Compound Brain Status section replaced with CQ section. History table started (Sessions 14/19/27/28 as baseline).
- **cross-wire-checklist.md:** Display format updated from `COMPOUND BRAIN: X/5` to `CQ: [score] (+/-N) | Trajectory: [label]`.
- **brain/metrics/:** CQ section added to S27 and S28 metrics files. All future metrics files include CQ dimensions.
- **Portability:** CQ framework is brain layer (methodology). Display format in cross-wire-checklist is runtime layer.

## 2026-03-21 — Session Cleanup Step Added to Wrap-Up
- **CLAUDE.md:** New step 12 added as final wrap-up step. Removes orphaned Claude Code project folders from `~/.claude/projects/`, keeping only `C--Users-olive-OneDrive-Desktop-Sprites-Work` and `C--Users-olive-SpritesWork-brain`. Reports count removed and remaining. Added to always-run list.
- **Portability:** Runtime layer, Windows-specific (PowerShell). Not SDK-portable.

## 2026-03-21 — 10-Gap Architecture Closure (Friston→Taleb→Dalio)
- **#1 Simulation Layer:** Layer 2.5 SIMULATE added to action-waterfall.md. Generates 2-3 candidates, scores against PATTERNS.md, predicts outcomes, logs for calibration. Prediction error feeds CW-5 + self-model. SDK-portable (brain methodology).
- **#2 Self-Model:** brain/self-model.md created. Reliability per output type, known blind spots, resource state. Read at session start. Feeds System 1/2 routing. Brain layer.
- **#3 System 1/System 2:** Layer 2.7 ROUTE added to action-waterfall.md. FAST track (reliability >0.9, SIMPLE, no provisionals) vs DELIBERATE track (full waterfall). Demotion on correction. Runtime layer.
- **#4 Rule Constitution:** 5 meta-rules added to .carl/global (CONSTITUTION_1-5). Testable failure conditions, no weakening CRITICAL rules, evidence-based creation, 5-rule cap per type, 20-session auto-flag. Oliver-only modification. Runtime layer.
- **#5 SLOs + Error Budgets:** 5 SLOs added to system-patterns.md (first-draft pass, gate completion, correction rate, calibration accuracy, wrap-up completion). Error budget consumed → investigation mode. Brain layer.
- **#6 Antifragility:** DS-5 Post-Failure Hardening added to cross-wire-checklist.md. Escalation triggers neighborhood stress test (3 closest components). Chaos frequency increases for 3 sessions. Runtime layer.
- **#7 Decision Journal:** Added to session note template in wrap-up skill. One-line format per major decision: what/alternatives/reason/confidence/revisit. Brain layer.
- **#8 Eval Suite:** brain/evals/ framework created with golden/, results/, README with capture protocol. Golden cases: 0/5, collecting during next prospect sessions. Brain layer.
- **#9 Agent Evolution:** Agent-local rules added to manifest-schema.md. Trust >= 2 agents can propose scoped rules. Same lifecycle as lessons. Cannot contradict CARL/safety/constitution. Both layers.
- **#10 Causal Chains:** Added to system-patterns.md. Tracks observed propagation chains with type (reinforcing/balancing) and value. 4 chains logged retroactively. Brain layer.
- **Sources:** Friston (Free Energy), LeCun (World Models), MuZero, Joscha Bach (MicroPsi), Kahneman (System 1/2), Anthropic (Constitutional AI), Google SRE, Taleb (Antifragile), Dalio (Radical Transparency), OpenAI (Evals), Netflix/Spotify (squad model), Senge (Fifth Discipline).

## 2026-03-21 — Cross-Wire v2: Three Trigger Classes + Utility Scoring
- **cross-wire-checklist.md:** Expanded from 12 event triggers to 3 classes: EVENT (CW-1→12, unchanged), TREND (CW-13→16, new), DANGER (DS-1→4, new). 20 total triggers.
- **TREND triggers (PID control theory):** CW-13 audit score drift (integral), CW-14 correction rate acceleration (derivative), CW-15 rule accumulation check (double-loop, every 5 sessions), CW-16 session type imbalance (variety).
- **DANGER signals (immune system theory):** DS-1 rapid correction burst (mid-session), DS-2 session duration anomaly, DS-3 orphan signal detection (requisite variety), DS-4 score-correction mismatch (homeostatic calibration).
- **Utility scoring (ACT-R):** Every cross-wire now has a continuous utility float (+1 per valuable fire, -1 per non-valuable). Negative utility = redesign candidate. Replaces binary fire/no-fire tracking.
- **system-patterns.md:** Cross-Wire Performance table restructured into 3 sections (Event/Trend/Danger) with utility column. Complexity budget updated.
- **CW-3 retroactive fix:** Lesson #70 (all-playbooks rule) promoted to DEMOPREP_RULE_2 in domain/carl/demo-prep. Should have fired in Session 14.
- **CLAUDE.md:** L3 Cross-Wiring description updated to reflect 3 trigger classes.
- **Portability:** Cross-wire architecture is BRAIN layer (methodology). Trigger definitions are SDK-portable. Utility scoring is SDK-portable.
- **Sources:** PID control theory (Wiener/Ashby), ACT-R utility learning (CMU), Argyris double-loop learning, Ashby's Law of Requisite Variety, biological danger theory (immune system).

## 2026-03-21 — Layer Split Execution (Brain / Runtime Extraction)
- **paths.py created** (RUNTIME) — All hardcoded paths extracted from config.py into brain/scripts/paths.py. Supports env var overrides (BRAIN_DIR, DOMAIN_DIR, WORKING_DIR, PYTHON_PATH, CLAUDE_CMD). To port to a new machine: edit paths.py only.
- **config.py cleaned** (BRAIN) — Now imports all paths from paths.py. Contains only portable config: embedding model, ChromaDB collections, file type map, RAG graduation, episodic memory, confidence scoring, outcome linking, query defaults. Zero hardcoded paths.
- **start.py updated** (RUNTIME) — Imports tool paths (PYTHON, CLAUDE_CMD) from paths.py instead of hardcoding.
- **/runtime/ skeleton created** — Four adapter directories: runtime/claude-code/, runtime/cursor/, runtime/api/, runtime/template/. Each has a README describing what moves there at extraction.
- **Verified:** All imports clean (config, paths, embed, query, launch, start). Full re-embed successful (94 chunks from 63 files).
- **Layer classification:** paths.py = RUNTIME. config.py = BRAIN. embed.py = BRAIN. query.py = BRAIN. launch.py = RUNTIME. start.py = RUNTIME. runtime/ = RUNTIME scaffolding.

## 2026-03-21 — Two-Layer Architecture (Brain / Runtime)
- **sdk-north-star.md:** Appended "Platform Universality" section defining brain layer (universal, platform agnostic) vs runtime layer (Claude Code specific adapters). Includes target folder structure for SDK extraction (/brain, /runtime/claude-code, /runtime/cursor, /runtime/api, /runtime/template). **SDK-portable.**
- **CLAUDE.md:** New "SDK Architecture" section — whole-picture rule loaded every session. Requires every architectural decision to be classified as brain layer or runtime layer before implementation. Brain = SDK-portable by default. Runtime = flagged as platform specific. **Runtime layer** (this rule governs Claude Code behavior).

## 2026-03-21 — Product Name Placeholders in SDK Files
- **sdk-north-star.md:** Replaced all instances of "the Starter SDK" and "the SDK" with [NAME]. Replaced "at SDK extraction" with "at [NAME] extraction".
- **sdk-audit.md:** Replaced all instances of "the Starter SDK" and "the SDK" with [NAME].
- **Why:** Product names are undecided. Placeholder tokens ensure no premature branding leaks into architecture docs.

## 2026-03-21 — Environment Section Added to CLAUDE.md
- **CLAUDE.md:** New "Environment" section — Windows OS, path conventions, Python/Node locations, PowerShell default.
- **Portability:** SDK-portable architecture decision. Any Starter SDK should capture the user's environment at onboarding so the agent knows the host OS, shell, and tool paths from session 1.

## 2026-03-21 — Periodic Audit Schedule
- **periodic-audits.md** created at .claude/periodic-audits.md — session-counted triggers for 4 recurring audits: /sdk-audit (every 5 sessions), memory index cleanup (every 10), RAG freshness check (every 3), config bloat scan (every 10).
- **Session start wired** — Phase 0.5 step 9 added to skills/session-start/SKILL.md. Checks audit schedule, queues due audits to appropriate phase (startup/session/wrap-up).
- **Component map updated** — Periodic Audits section added, RAG Pipeline descriptions updated to reflect episodic memory, confidence scoring, and outcome linking.
- **Portability:** Periodic audit schedule is SDK-portable (frequencies are generic). /sdk-audit is SDK-specific tooling.

## 2026-03-21 — SDK North Star + Boundary Enforcement
- **sdk-north-star.md** created at brain/vault/sdk-north-star.md — strategic context documenting the boundary between the Sprites Work operation (private, domain-specific) and the Starter SDK (open source, profession-agnostic compounding brain framework with marketplace layer). Sprites Work is the proof of concept, not the product.
- **sdk-audit.md** created at .claude/commands/sdk-audit.md — SDK boundary enforcement slash command. Scans CLAUDE.md, agents/registry.md, hook files, and RAG scripts for Sprites-specific contamination. Reports CONTAMINATED/REVIEW/CLEAN per file. Read-only — never auto-edits.
- **Portability:** Both are SDK-portable architecture decisions. The north star defines the extraction boundary; the audit enforces it.

## 2026-03-21 — Ad Platform Intelligence Integration (Session 25)
- **Source:** External Claude Code config review (zip file with agents/skills for Sprites product dev)
- **CLAUDE.md:** Added context hygiene rule (compact at 50%) and anti-mediocrity rule (scrap mediocre drafts, rebuild clean)
- **CARL:** GLOBAL_RULE_4 (context hygiene), LISTBUILD_RULE_8 (ad platform signal detection)
- **Quality rubrics:** Anti-mediocrity rule (score 5-6 = scrap and rebuild, don't patch)
- **New files:** domain/reference/meta-api-patterns.md, domain/reference/google-ads-patterns.md
- **Demo prep gate:** Steps 9b (ad platform audit) + 9c (thread flow design) — analyze prospect's ad setup, map Sprites threads to their specific ROAS gaps
- **Lead filtering SOP:** Step 4b (ad platform signal detection) — free website scan adds 7 columns (meta_pixel, google_ads, google_analytics, gtm, ad_platforms, likely_budget_tier, top_roas_gap)
- **Memory:** feedback_concurrent_sessions.md — Oliver runs up to 3 terminals concurrently, verify session numbers before writing

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
