# System Evolution — Build History, Attribution & Current State

> Last updated: 2026-03-20 (after CARL compaction + missing file creation)
> Current state: 114 behavioral CARL rules across 9 domains. CLAUDE.md at 120/150 lines.
> Files: soul.md, context-manifest.md, .agentignore all live. System is post-compaction.

---

## Original Architecture — Built by Oliver

Oliver built the entire foundational system from scratch for his full-cycle AE workflow at Sprites.ai. No external skill, template, or framework was used as a starting point. Everything below was designed by Oliver across Sessions 1-8 (March 18-19, 2026).

### Five-Layer Self-Improvement Architecture
- **L1 Loop** — Tag every sales interaction, track outcomes, aggregate patterns, make the next action smarter.
- **L2 System Loop** — Track whether the system's own components (gates, lessons, smoke checks, audits) are working. Dead weight gets flagged.
- **L3 Cross-Wiring** — Seven bidirectional connections (LOOP_RULE_28-34): auditor→gates, gates→lessons, lessons→CARL, smoke→lessons, rubric drift→tighten, fallback→reorder, PATTERNS→gates. *(v2.0: replaced by hooks + event queries)*
- **L4 Meta-Loop** — Track which cross-wire connections produce value (LOOP_RULE_35-36). Kill dead wires, strengthen high-value ones. Runs every 5 sessions. *(v2.0: killed — premature abstraction)*
- **L5 Convergence** — Auto-detect maturity (LOOP_RULE_37-38). Kill switches: 5 cycles zero value = auto-disable. Max 3 active layers. *(v2.0: killed — premature abstraction)*

No external source informed this architecture.

### CARL Rule Engine
Custom rule engine. Post-compaction state: 114 behavioral rules + 43 command rules = 157 total across 10 domains.

| Domain | Rules | Type |
|--------|-------|------|
| global | 4 | ALWAYS_ON |
| loop | 60 | ALWAYS_ON |
| agents | 9 | On-demand |
| context | 3 | ALWAYS_ON |
| coldcall | 7 | On-demand |
| demo-prep | 8 | On-demand |
| linkedin | 6 | On-demand |
| listbuild | 9 | On-demand |
| prospect-email | 8 | On-demand |
| commands | 43 | On-demand (excluded from behavioral count) |

Features: manifest-driven loading, ALWAYS_ON vs keyword-triggered (RECALL) domains, priority system (CRITICAL/HIGH/NORMAL), shadow mode for rule testing, exclusion patterns, skill contracts (READS/WRITES/REQUIRES).

Compaction history: Started at 187 behavioral rules (Session 8). Compacted to 114 (Session 9). Retired 24 duplicates, merged 55→16, moved 12 deck format rules to reference file.

### Mandatory Gates (8 gates in .claude/gates.md)
- Pre-Draft (7-step research + checkpoint + approval before any email)
- Demo Prep (8-step research + story-trap structure)
- Post-Demo Follow-Up (Fireflies transcript mandatory)
- Cold Call Script (LinkedIn visit mandatory)
- LinkedIn Message (profile visit + personal hook)
- Pipedrive Note Quality (verified data only, schema validation)
- Win/Loss Analysis (debrief on every close)
- Lead Filtering (filter before enrich, score in one pass)

### Multi-Agent Architecture (.carl/agents — 9 rules)
Five agent types with hard boundaries: Research (no drafting), Draft (no research), CRM (no drafting), Audit (independent scoring), Orchestrator (coordination only). Input/output contracts, pipeline rules, cost control (max 5 agents/session).

### Obsidian Vault / Brain System
- Prospect notes with structured templates (brain/prospects/)
- Persona patterns (brain/personas/)
- Pipeline tracking (brain/pipeline/)
- Knowledge graph with query-playbook function
- Git-versioned with semantic versioning (brain/VERSION.md)
- Session handoff via brain/loop-state.md
- SQLite backing store (brain/system.db)

### Voice & Writing Identity (soul.md — created Session 9)
Extracted from CLAUDE.md to its own file: writing voice, banned words, tone rules, email frameworks (CCQ/Inbound/Follow-Up), email structure, persona boundaries, humanizer pass, signature. CLAUDE.md references soul.md — no duplication.

### Context Management (context-manifest.md + .agentignore — created Session 9)
Four-tier lazy loading: Tier 0 always in context (~8k tokens), Tier 1 startup checks (read/summarize/release), Tier 2 task-triggered, Tier 3 excluded (.agentignore). Replaced 10-line startup sequence in CLAUDE.md with 2-line manifest pointer. CLAUDE.md freed from 151→120 lines.

### Closed-Loop Sales Intelligence (Loop — 60 rules)
Universal learning engine covering the full deal lifecycle:
- Two-tier tracking (COLD from Instantly bulk, PIPELINE from personalized touches)
- Structured tag taxonomy with closed angle set (25 angles)
- Confidence tiers (<3 to 100+ data points)
- Cadence rules with data-driven overrides
- Deal health scoring (0-100) with close probability (LOOP_RULE_39)
- Signal monitoring — 5 signal types with relevance scoring (LOOP_RULE_41)
- Framework auto-promotion at 40%+ conversion (LOOP_RULE_40)
- Compound experiments with max 3 concurrent (LOOP_RULE_42)
- Vault decay — prospects 90d, personas 60d, objections 120d (LOOP_RULE_54-56)
- Micro-reflection trigger on every system addition (LOOP_RULE_59)

### Enterprise Quality System (14 governance files)
quality-rubrics.md | fallback-chains.md | auditor-system.md | health-audit.md | loop-audit.md | gates.md | pipedrive-templates.md | weekly-pulse-template.md | audit-log.md | review-queue.md | changelog.md | truth-protocol.md | micro-reflections.md

---

## External Ideas Applied — By Source

### Anthropic / Constitutional AI
**Concept:** Agent follows written rules as its constitution, with checks to prevent drift.
**Applied:** Calibration system in auditor-system.md. Self-assessment needs external checking, not just rule-following.
**Portability:** DOMAIN-AGNOSTIC

### OpenAI / RLHF
**Concept:** Human preference data corrects model behavior over time.
**Applied:** Oliver's score overrides feed rubric adjustments. 5+ overrides on same type → auto-adjust. Calibration accumulation with recency weighting, max correction ±4.
**Portability:** DOMAIN-AGNOSTIC

### OpenAI / Critic Separation
**Concept:** Draft and audit agents score independently. Self-scores redacted before audit.
**Applied:** auditor-system.md hard separation rule. 2+ point divergence = most valuable calibration signal.
**Portability:** DOMAIN-AGNOSTIC

### Google DeepMind / Self-Play
**Concept:** Agent plays both sides — drafts output AND generates the prospect's objection.
**Applied:** Self-Play Objection Check in all 4 outbound gates (Pre-Draft, Post-Demo, Cold Call, LinkedIn).
**Portability:** SALES-SPECIFIC (generalizes to "adversarial self-review")

### Google / Search Quality Raters
**Concept:** Human raters with detailed rubrics calibrate algorithms.
**Applied:** Weekly calibration prompt, drift detection (3+ consecutive divergences → auto-tighten).
**Portability:** DOMAIN-AGNOSTIC

### Perplexity / Grounded Citations
**Concept:** Every factual claim grounded in a specific source, cited inline.
**Applied:** Claim-level source tagging in CRM notes and demo cheat sheets. "[45 employees [Apollo]]"
**Portability:** DOMAIN-AGNOSTIC

### Meta / RAG Retrieval
**Concept:** Query with specific questions, not whole-document loads.
**Applied:** Vault research step queries with "What do I know about [person]?" instead of reading full files.
**Portability:** DOMAIN-AGNOSTIC

### Cursor Architecture
**Concept:** Lazy context loading, research receipts, task queuing, .agentignore.
**Applied:** context-manifest.md (4-tier loading), .agentignore (file exclusions). Both now live files created in Session 9.
**Portability:** DOMAIN-AGNOSTIC

### NVIDIA / INT8 Calibration
**Concept:** Representative data finds optimal scaling factors.
**Applied:** Calibration accumulation — corrections compound with recency weighting.
**Portability:** DOMAIN-AGNOSTIC

### Manus / Agent Self-Reflection
**Concept:** Agents self-evaluate, humans verify, gap trains better self-evaluation.
**Applied:** Calibration delta tracking (self-score → Oliver score → delta).
**Portability:** DOMAIN-AGNOSTIC

### ClawHub: pskoett/self-improving-agent
**Applied:** Structured entry IDs (LRN/ERR), status lifecycle (PENDING→PROMOTED), recurrence tracking (Pattern-Key + counts), promotion trigger (≥3 across ≥2 sessions in 30 days), error separation, feature request capture.
**Portability:** DOMAIN-AGNOSTIC

### ClawHub: ivangdavila/self-improving
**Applied:** Corrections rolling buffer (last 20), data compaction (merge similar), conflict resolution hierarchy (GLOBAL_RULE_3, was GLOBAL_RULE_15 pre-compaction).
**Portability:** DOMAIN-AGNOSTIC

### ClawHub: oswalpalash/ontology
**Applied:** Schema validation for CRM notes (required fields, format checks), append-only mutation log in truth-protocol.md, skill contracts in .carl/manifest.
**Portability:** DOMAIN-AGNOSTIC

### ClawHub: fly0pants/admapix
**Applied:** Request complexity classification (SIMPLE/STANDARD/DEEP) as GLOBAL_RULE_2 (was GLOBAL_RULE_14 pre-compaction).
**Portability:** DOMAIN-AGNOSTIC

### Ironsail / Genus OS (github.com/Ironsail-llc/genus-os)
**Concept:** Multi-tenant agent OS with declarative manifests, graduated trust, escalation ladders, tool allow/deny lists, budget cascades, and post-execution verification.
**Applied (Session 21 — Tranche 1):**
- Agent manifest schema (structured markdown, not YAML) — second universal standard alongside Score. agents/manifest-schema.md
- Tool allow/deny per agent in manifests — formal permission boundaries
- Graduated trust scoring — correction_rate tracks over 5 sessions, gates autonomy scope (config-only → config+instructions → config+instructions+code). Adapted from Nightwatch merge-rate trust.
- Auto-pause circuit breaker — 3 consecutive rejections = SYSTEM_PAUSE signal
- In-task escalation ladder — 3 errors=change strategy, 4=reduce scope, 5=stop. Extended fallback-chains.md.
- 5-Point Verification Stack consolidation — replaced 9-step verification with 5 distinct questions (INPUT→GOAL→ADVERSARIAL→VOICE→SCORE). Added GOAL check (the question we were missing: "is this what was asked for?"). Removed overlap between Layer 5 verify, gate checklist, and separated scoring sub-steps.
- Agent scaffold skill — generates manifests from schema with nervous system wiring
- 4 new bus signals: TOOL_DENIED, SYSTEM_PAUSE, ESCALATION_TRIGGERED, AGENT_CREATED *(v2.0: bus signals now emitted via events.py)*
- 3 new cross-wires: CW-10 (Tool Violation→Manifest Fix, dormant), CW-11 (Correction Rate→Autonomy Scope), CW-12 (Escalation→Lessons) *(v2.0: cross-wires replaced by hooks + event queries)*
**What was NOT borrowed:** YAML format (we use structured markdown), Redis/PostgreSQL infrastructure, server daemon architecture, workflow engine (we don't need declarative pipelines), heartbeat system (session-based, not always-on).
**Portability:** DOMAIN-AGNOSTIC (all governance patterns, no sales-specific content)

---

## What Oliver Built vs What Was Borrowed

### Oliver Built From Scratch:
- Five-layer recursive self-improvement architecture (L1-L5)
- CARL rule engine with domains, manifest loading, priority, shadow mode
- All 8 mandatory research gates
- Loop sales intelligence with two-tier tracking, tag taxonomy, confidence tiers, cadence
- Multi-agent architecture with hard boundaries
- Obsidian vault with prospect templates, persona patterns, knowledge graph
- Session startup/wrap-up with mandatory steps and 8.0 hard gate
- Ping-pong audit protocol
- Deal health scoring and predictive pipeline
- Signal monitoring (5 signal types)
- Framework auto-promotion and dead framework archival
- Compound experiments
- Complexity ceilings and kill switches
- Cross-wire connections (7 bidirectional links) *(v2.0: replaced by hooks + event queries)*
- Meta-loop tracking *(v2.0: killed)*
- Convergence detection with auto-disable *(v2.0: killed)*
- Truth protocol
- Bloat prevention and compaction rules
- Session handoff system (loop-state.md)
- Email frameworks (CCQ, Inbound, Follow-Up)
- Cost hierarchy (FREE FIRST)
- Humanizer integration
- Action waterfall (5-layer output pipeline)
- Pre-flight proof blocks and post-draft tag blocks
- Pipeline-first mandate and same-session testing
- soul.md voice identity extraction
- Vault decay (prospect 90d, persona 60d, objection 120d)
- Micro-reflection trigger on system additions

### Borrowed and Adapted:
- Calibration system inspiration from Anthropic, OpenAI, Google, NVIDIA, Manus
- Critic separation (OpenAI → self-score redaction)
- Self-play objection checking (DeepMind → adversarial draft review)
- Grounded citations (Perplexity → claim-level source tagging)
- Question-driven retrieval (Meta RAG → vault queries)
- Context manifest + .agentignore (Cursor → lazy loading + file exclusion)
- Structured IDs, lifecycle, recurrence, error separation, feature requests (pskoett)
- Corrections buffer, data compaction, conflict resolution (ivangdavila)
- Schema validation, mutation log, skill contracts (ontology)
- Request complexity classification (admapix)

### The Honest Summary:
Oliver built approximately 85% of the system independently. External sources contributed ~15%, primarily in calibration theory (AI lab practices) and learning system mechanics (ClawHub skills). The most structurally significant external contribution is the Cursor-inspired context management, now live as context-manifest.md.

What's distinctive is the integration density. No external source had the five-layer recursion, cross-wiring, meta-loop, or convergence detection. No ClawHub skill had mandatory gates, deal health scoring, or framework auto-promotion. The borrowed improvements are refinements to an architecture more sophisticated than any individual source.

---

## SDK Portability Table

| Component | Source | Portability | Notes |
|-----------|--------|-------------|-------|
| Five-layer self-improvement | Oliver | STRUCTURAL | Core architecture, always ships |
| CARL rule engine | Oliver | STRUCTURAL | Domain files swappable; engine universal |
| Mandatory gates | Oliver | STRUCTURAL / SALES-SPECIFIC | Gate framework ships; checklist content is domain-specific |
| Loop (sales intelligence) | Oliver | SALES-SPECIFIC | Abstract to "Domain Intelligence Engine" for SDK |
| Multi-agent boundaries | Oliver | STRUCTURAL | Agent roles domain-specific, boundary system universal |
| Vault / brain integration | Oliver | STRUCTURAL | Directory structure agnostic; templates domain-specific |
| Session startup/wrap-up | Oliver | STRUCTURAL | Sequence universal; specific checks domain-specific |
| Context manifest + .agentignore | Oliver + Cursor | DOMAIN-AGNOSTIC | Universal context management |
| soul.md (voice identity) | Oliver | SALES-SPECIFIC | Voice rules are domain-specific; extraction pattern is universal |
| Ping-pong audit | Oliver | DOMAIN-AGNOSTIC | Works for any professional domain |
| Calibration system | Oliver + AI labs | DOMAIN-AGNOSTIC | Mechanics universal; rubric content domain-specific |
| Truth protocol | Oliver | DOMAIN-AGNOSTIC | Evidence-based operation works everywhere |
| Critic separation | OpenAI | DOMAIN-AGNOSTIC | Self-score redaction works for any output |
| Self-play objection check | DeepMind | SALES-SPECIFIC | Generalizes to "adversarial self-review" |
| Grounded citations | Perplexity | DOMAIN-AGNOSTIC | Any domain with factual claims |
| Question-driven retrieval | Meta RAG | DOMAIN-AGNOSTIC | Query with questions, not file loads |
| Structured lesson IDs | pskoett | DOMAIN-AGNOSTIC | LRN/ERR IDs work everywhere |
| Status lifecycle | pskoett | DOMAIN-AGNOSTIC | PENDING→PROMOTED works everywhere |
| Recurrence tracking | pskoett | DOMAIN-AGNOSTIC | Pattern-Key + counts universal |
| Corrections buffer | ivangdavila | DOMAIN-AGNOSTIC | Rolling correction log universal |
| Data compaction | ivangdavila | DOMAIN-AGNOSTIC | Any pattern store needs compaction |
| Conflict resolution | ivangdavila | DOMAIN-AGNOSTIC | Rule priority hierarchy universal |
| Schema validation | ontology | DOMAIN-AGNOSTIC / SALES-SPECIFIC | Engine ships; fields domain-configured |
| Mutation log | ontology | DOMAIN-AGNOSTIC | Append-only audit trail universal |
| Skill contracts | ontology | DOMAIN-AGNOSTIC | READS/WRITES/REQUIRES universal |
| Complexity classification | admapix | DOMAIN-AGNOSTIC | SIMPLE/STANDARD/DEEP universal |
| Confidence flagging | Oliver | DOMAIN-AGNOSTIC | HIGH/MEDIUM/LOW on every output |
| Reasoning blocks | Oliver | DOMAIN-AGNOSTIC | Explain thinking before output |
| Oliver's Summary | Oliver | DOMAIN-AGNOSTIC | Plain-English debrief for any stakeholder |
| Confidence decay | Oliver | DOMAIN-AGNOSTIC | 90-day decay for any pattern store |
| Vault decay | Oliver | DOMAIN-AGNOSTIC | Aging + archival works for any knowledge base |
| Micro-reflections | Oliver | DOMAIN-AGNOSTIC | Integration check on additions works everywhere |
| Cold dataset feedback | Oliver | SALES-SPECIFIC | Instantly data feeding Loop is sales-only |

**SDK Summary:** 25 DOMAIN-AGNOSTIC (ship as-is) | 5 SALES-SPECIFIC (need abstraction) | 6 STRUCTURAL (always ship)

---

## Current System Score (Post-Compaction Baseline)

Scored using the 5 auditor dimensions from auditor-system.md, against the quality-rubrics.md benchmark.

| Dimension | Score | Rationale | Path to 9.0+ |
|-----------|-------|-----------|---------------|
| **Research Depth** | 8.0 | Gates enforce multi-source research with question-driven retrieval, pre-flight proof blocks, and research receipts. soul.md ensures voice consistency. Gap: only 1 pipeline session (Session 5) has run the full gate pipeline with real prospects. | 10+ prospect interactions through the complete gate pipeline. Verify receipts are genuine, not rubber-stamped. |
| **Output Quality** | 7.5 | Rubrics exist for every output type. Humanizer, self-play objection check, confidence flags live. soul.md centralizes voice rules (no duplication drift). Gap: only 3 calibration events exist (all demo_prep, delta narrowing from -1 to -0.2). No email or CRM note calibration data. | 10+ Oliver score overrides across output types. Calibration accumulation adjusts rubrics from real data. |
| **Process Adherence** | 8.5 | 114 CARL rules (compacted from 187 — cleaner, fewer conflicts). 8 mandatory gates. Context manifest controls loading. Wrap-up gate enforced. Conflict resolution hierarchy active. Gap: Session 6 proved rules can exist without being followed. *(v2.0: PROVISIONAL format replaced by [INSTINCT:X.XX] confidence scoring.)* | Track gate completion rates over 10 sessions. Update instinct confidence scores at each wrap-up. Verify the compacted rule set eliminates the hedging behavior seen at 187 rules. |
| **Learning Capture** | 8.0 | Structured lesson IDs, status lifecycle, recurrence tracking, corrections buffer, data compaction, micro-reflections. 50 graduated lessons, 35 active. Gap: the structured format (LRN-/ERR- IDs, Pattern-Key, recurrence counts) has never been used in practice. All current lessons use the old freeform format. | 5 sessions with the structured format. Verify recurrence tracking fires, compaction works, promotion triggers produce real rules. |
| **Outcome Linkage** | 6.0 | Deal health scoring, close probability, signal monitoring, and framework auto-promotion designed but uncalibrated. 0 closed deals to validate against (Matt Cosprite was onboarding, not closed-won in Pipedrive). Vault decay and weekly health metrics in place but no baseline data collected yet. | Close 15+ deals. Let deal health calibrate. Let framework auto-promotion fire on real data. This dimension improves last — it's a lagging indicator. |

**Overall Baseline: 7.6 / 10**

The system is architecturally mature but execution-thin. The compaction improved Process Adherence (fewer rule conflicts, cleaner loading) without sacrificing coverage. The extraction of soul.md and creation of context-manifest.md improved structural clarity. The path to 9.0+ requires sustained pipeline work through the existing gates — the architecture is ready, the data isn't.

---

## Rule Density Analysis

### Post-Compaction State: 114 Behavioral Rules

| Tier | Purpose | Target | Actual | Status |
|------|---------|--------|--------|--------|
| Tier 1 | Hard constraints (never fabricate, never send without approval) | 10-15 | ~12 | ON TARGET |
| Tier 2 | Process rules (research order, CRM format, startup, wrap-up) | 20-30 | ~35 | SLIGHTLY OVER — some process rules could graduate to reference files |
| Tier 3 | Learning rules (self-improvement loop, compaction, decay) | 15-20 | ~25 | OVER — vault decay (3) and micro-reflection (1) are new, untested |
| Tier 4 | Domain rules (ICP, email, persona, demo format) | 10-15 | ~42 | OVER — 6 domain files with operational rules |

The system is 14 rules over the 100-rule ceiling. The overage is concentrated in Tier 2 (process) and Tier 4 (domain). Domain rules are the next compaction candidate — many contain NotebookLM notebook IDs and specific query templates that could move to reference files, similar to how deck format rules moved to docs/Demo Prep/deck-template.md.

### Compaction Log

| Date | Session | Before | After | Method | Details |
|------|---------|--------|-------|--------|---------|
| 2026-03-20 | 9 | 187 | 114 | Full compaction | 24 retired (12 Claude Code defaults, 6 meta-descriptions, 3 CLAUDE.md duplicates, 3 overlap/circular). 55→16 merged (bloat 6→2, meta-loop 5→2, convergence 5→2, predictive 3→1, playbooks 3→1, signals 3→1, agents 12→4, context 16→3). 12 moved to docs/Demo Prep/deck-template.md. |
