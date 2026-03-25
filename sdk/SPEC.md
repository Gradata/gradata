# AIOS Brain SDK — Unified Specification
# Synthesized from: Build Directive + Engineering Spec + Revised Vision
# Date: 2026-03-24 (Session 42)
# Status: Active — this is the single source of truth

## PRINCIPLE
The system is allowed to fail. It is not allowed to lie.

---

## 1. WHAT THIS IS

An AI brain is a behavioral configuration that sits on top of any LLM and makes it an expert at a specific domain. Unlike static memory or fine-tuning, a brain compounds through use:

1. User works with AI normally
2. AI gets something wrong → user corrects it
3. Corrections are logged, classified, and graduated into behavioral rules
4. Over time: fewer corrections, higher first-draft acceptance, domain expertise that compounds

The brain is portable (a self-contained directory with SQLite + markdown), verifiable (quality scores from real data), and domain-specific (trained over hundreds of sessions).

### The Graduation Pipeline (core innovation)

```
INSTINCT (0.0-0.59) → PATTERN (0.60-0.89) → RULE (0.90+)

Promotion requires:
  - Real application (min 3 for PATTERN, min 5 for RULE)
  - No promotion from silence
  - Aggressive demotion on misfire (-0.25)
  - Scoped per domain/task_type/audience/channel/stakes

Kill switches by maturity (RELEVANT cycles only — irrelevant sessions don't count):
  INFANT (0-50 sessions): 15 relevant cycles zero value
  ADOLESCENT (50-100): 12 relevant cycles
  MATURE (100-200): 10 relevant cycles
  STABLE (200+): 8 relevant cycles

Renter mode: lessons are FROZEN. No confidence changes, no auto-kills.
Renters can flag lessons as unhelpful (misfired) but compound knowledge is preserved.
```

---

## 2. ARCHITECTURE (3 layers)

```
Layer 0: patterns/     — 15 base agentic patterns (pure Python, zero deps)
Layer 1: enhancements/ — compound learning system (imports from patterns/)
Layer 2: brain/        — trained data (user's domain expertise)

Rules:
  - patterns/ NEVER imports from enhancements/
  - enhancements/ ALWAYS imports from patterns/
  - brain.py is the composition layer wiring both together
```

### Layer 0: Base Patterns (15 modules)
| Pattern | Module | Purpose |
|---------|--------|---------|
| Orchestrator | orchestrator.py | Session classification, pattern selection |
| Router/Scope | scope.py | Domain-agnostic task typing, audience detection |
| Pipeline | pipeline.py | Sequential stages with quality gates |
| Parallel | parallel.py | Dependency graph, wave execution |
| Human Loop | human_loop.py | Risk-tiered approval gates |
| Sub-Agents | sub_agents.py | Structured delegation with contracts |
| Reflection | reflection.py | Generate-critique-refine loop |
| Evaluator | evaluator.py | Score-gated optimize loop |
| Memory | memory.py | 3 types: episodic/semantic/procedural |
| Guardrails | guardrails.py | Input/output guards (PII, injection, banned phrases) |
| RAG | rag.py | Cascade: FTS→Vector→Hybrid→Two-Pass expansion, graduation-aware scoring (RULE=1.2x, INSTINCT=0.8x) |
| Rule Engine | rule_engine.py | Scope-aware rule selection + prompt injection |
| Rule Tracker | rule_tracker.py | RULE_APPLICATION event logging |
| Tools | tools.py | Tool registry + plan-before-execute |
| MCP | mcp.py | Brain-to-host protocol bridge |

### Layer 1: Enhancements (16 modules)
| Enhancement | Module | Purpose |
|-------------|--------|---------|
| Self-Improvement | self_improvement.py | INSTINCT→PATTERN→RULE graduation (user corrections) |
| **Agent Graduation** | **agent_graduation.py** | **Same graduation pipeline applied to agent/subagent outputs. Human approval gate that graduates from CONFIRM→PREVIEW→AUTO. Upward distillation of agent learnings to brain level.** |
| Diff Engine | diff_engine.py | Edit distance + 5-level severity |
| Edit Classifier | edit_classifier.py | 5-category classification (tone/content/structure/factual/style) |
| Pattern Extractor | pattern_extractor.py | Extract patterns from classified edits |
| Metrics | metrics.py | Rolling window quality metrics from events |
| Failure Detectors | failure_detectors.py | 4 automated regression alerts |
| Reports | reports.py | Health, CSV, metrics, rule audit reports |
| Success Conditions | success_conditions.py | 6-condition validation from Build Directive |
| CARL | carl.py | Behavioral contracts per domain |
| Quality Gates | quality_gates.py | 8.0 threshold with fix cycling |
| Truth Protocol | truth_protocol.py | Evidence-based output validation |
| Correction Tracking | correction_tracking.py | Density, half-life, MTBF/MTTR |
| Brain Scores | brain_scores.py | Compound health metric (report card) |
| **Judgment Decay** | **judgment_decay.py** | **Confidence decay for idle lessons, reinforcement for applied ones, UNTESTABLE archival** |
| **Rules Distillation** | **rules_distillation.py** | **Cross-lesson pattern detection, rule promotion proposals with evidence scoring** |

### Layer 2: Trained Brain (user's data)
```
brain/
  system.db              — SQLite: events table (event-sourced, all data)
  events.jsonl           — Append-only portable event log
  brain.manifest.json    — Quality + capability declaration
  taxonomy.json          — Domain-specific tag vocabulary (optional, sales defaults if absent)
  lessons.md             — Active lessons (INSTINCT/PATTERN/RULE with confidence scores)
  prospects/             — Semantic memory: domain entities (or candidates/, projects/, etc.)
  sessions/              — Episodic memory (session notes)
  emails/PATTERNS.md     — Procedural memory (what works)
```

---

## 3. CORE LOOP (from Engineering Spec)

```
User Prompt
  → AI Draft (brain.log_output)          ← caller invokes
  → User Edits / Corrections
  → Final Output
  → Diff Engine (compute_diff)           ← brain.correct() handles automatically
  → Edit Classifier (classify_edits)     ← brain.correct() handles automatically
  → CORRECTION event emitted             ← brain.correct() handles automatically
  → Pattern Extraction (extract_patterns)← brain.correct() handles automatically
  → Scoped Graduation (update_confidence)← caller invokes separately (or wrap-up)
  → Rule Application (apply_rules)       ← brain.apply_brain_rules() before next draft
  → Metrics Update (compute_metrics)     ← on-demand via brain.health() or CLI report
```

### What's automatic vs manual

| Step | Method | When |
|------|--------|------|
| Log output | `brain.log_output(text, type, score)` | Before user sees draft |
| Record correction + extract patterns | `brain.correct(draft, final)` | After user edits (auto-extracts patterns) |
| Apply rules | `brain.apply_brain_rules(task, ctx)` | Before next draft (prompt injection) |
| Graduate rules | `update_confidence(lessons, corrections)` | Session wrap-up |
| Compute metrics | `compute_metrics(db_path, window)` | On-demand or wrap-up |

The host runtime (Claude Code, Cursor, etc.) is responsible for calling these at the right time.
The SDK provides the functions; it does NOT auto-run the full loop in a single call.
The MCP server exposes `brain_correct` and `brain_log_output` as tools for host integration.

### Correction Detection (known challenge)

MCP protocol has NO concept of user feedback or corrections. Correction signals vary by host:
- Claude Code: partial (hooks exist for PostToolUse)
- Cursor: partial (hooks in beta)
- Claude Desktop: zero correction detection

**Solution:** `sidecar/watcher.py` — an out-of-band file watcher that detects edits independently
of the MCP stdio channel. Content hash dedup with 30-second window prevents double-counting.
Falls back to explicit `brain_correct()` tool calls for hosts without hooks.
The `<private>` tag convention (`rag.py:strip_private()`) excludes marked content from tracking.

---

## 3B. AGENT GRADUATION (compounding agent behavioral adaptation)

The graduation pipeline applies at THREE levels, not just user corrections:

```
Level 0: User trains brain           (user corrects AI → lessons graduate)
Level 1: Brain trains its agents     (orchestrator evaluates agent output → agent lessons graduate)
Level 2: Agents train subagents      (agent evaluates subagent → subagent lessons graduate)
```

### How It Works

Each agent type (research, writer, critic, etc.) maintains its own behavioral profile:
- lessons.md (INSTINCT→PATTERN→RULE, same graduation mechanics)
- profile.json (FDA rate, approval gate state, quality history)
- outcomes.jsonl (append-only evaluation log)

When an agent produces output:
1. Orchestrator (or user) evaluates: approved / edited / rejected
2. Edits become CORRECTION signals feeding the agent's graduation pipeline
3. Approvals boost lesson confidence (+0.05 per approval)
4. Rejections penalize (-0.25, same loss aversion as user-level)

### Human Approval Gate Graduation

The approval gate ITSELF graduates based on the agent's track record:

```
CONFIRM (sessions 0-10):  Oliver must review every agent output
  → After 70% FDA across 10+ outputs:
PREVIEW (sessions 10-25): Oliver sees summary, quick approve/reject
  → After 90% FDA across 25+ outputs:
AUTO (sessions 25+):      Agent auto-executes, spot-check only
  → 3 consecutive rejections: DEMOTE one level
```

New agent types ALWAYS start at CONFIRM. Trust is earned, not assumed.

### Upward Distillation

Agent learnings that prove valuable (reach PATTERN or RULE) distill upward:
- Subagent PATTERN → offered to parent agent
- Agent RULE → offered to brain-level lessons
- Cross-agent patterns propagate through the brain layer

```python
# API
brain.agent_graduation.record_outcome("research", output, "approved")
brain.agent_graduation.record_outcome("writer", output, "edited", edits="...")
gate = brain.agent_graduation.get_approval_gate("research")  # "auto"
rules = brain.agent_graduation.get_agent_rules("research")   # for prompt injection
distilled = brain.agent_graduation.distill_upward()           # brain-level enrichment
```

### Agent Manifest

Each trained agent gets quality proof (per-agent brain.manifest):
```json
{
  "agent_type": "research",
  "sessions_trained": 47,
  "maturity_phase": "ADOLESCENT",
  "fda_rate": 0.89,
  "approval_gate": "auto",
  "proven_rules": 12,
  "lessons": {"RULE": 3, "PATTERN": 5, "INSTINCT": 4}
}
```

This makes trained agents independently rentable — not just the brain, but the
specialized agents within it, each with provable quality metrics.

---

## 4. DATA MODEL (event-sourced)

All data lives in the `events` table. No separate domain tables.

### Event Types (20+)
| Type | Purpose | Data fields |
|------|---------|-------------|
| OUTPUT | AI-generated content | output_text, output_type, self_score, prompt, outcome, major_edit |
| CORRECTION | User edited output | draft_text, final_text, edit_distance, severity, category, classifications |
| RULE_APPLICATION | Rule was applied | rule_id, accepted, misfired, contradicted, scope |
| CALIBRATION | Self-score vs reality | brier_score, calibration_rating, predictions |
| DELTA_TAG | Activity logging | prospect, activity_type, outcome |
| HUMAN_JUDGMENT | User accept/reject | accepted, edit_flag, reasoning |
| AUDIT_SCORE | Session quality | combined_avg, dimensions |
| GATE_RESULT | Gate compliance | gate, result, sources_checked |
| LESSON_CHANGE | Lesson transition | from_state, to_state, confidence |
| HEALTH_CHECK | System liveness | stale_files, brain_alerts |
| SESSION_CLOSE | Session end marker | session_type, duration |
| STEP_COMPLETE | Task step finished | step_name, duration_ms |
| AGENT_SPAWN | Sub-agent launched | agent_type, task |
| AGENT_VERIFY | Agent output verified | agent_id, verdict |
| TOOL_FAILURE | Tool call failed | tool_name, error, fallback_used |
| VERIFICATION | Output verified | method, passed, detail |
| DEFER | Task deferred | reason, deferred_to |
| COST_EVENT | Credit/cost tracking | tool, credits_used, balance |
| REFLECT_PROCESSED | Reflection completed | lessons_updated, corrections_reviewed |

### Output Classification (5 levels)
| Level | Edit Distance | Meaning |
|-------|--------------|---------|
| as-is | < 0.02 | Accepted unchanged |
| minor | < 0.10 | Small tweaks |
| moderate | < 0.30 | Significant edits |
| major | < 0.60 | Heavy rewrite |
| discarded | >= 0.60 | Replaced entirely |

### Rule Tracking Fields
- applied: rule was surfaced to the prompt
- accepted: output conformed to the rule
- misfired: rule was irrelevant to the task
- contradicted: output explicitly violated the rule

---

## 5. METRICS + SUCCESS CONDITIONS

### Rolling Metrics (from Build Directive)
- Rewrite rate (% major/discarded)
- Edit distance (average across outputs)
- Acceptance distribution (histogram of 5 levels)
- Rule success/misfire rates
- Blandness score (vocabulary diversity)
- Correction density per session

### Success Conditions (ALL must be true across 20+ sessions)
1. Correction rate decreases
2. Edit distance decreases
3. First-draft acceptance increases
4. Rule success rate increases
5. Misfire rate stays low or decreases
6. Output does NOT become more generic (blandness < 0.70)

### Failure Detectors (automated alerts)
- Corrections drop but edits don't → brain being ignored
- Acceptance rises but quality flat → brain playing safe
- Rules increase but misfires increase → brain overfitting
- Output becomes bland (blandness score > 0.70 inverted TTR) → regression to mean

---

## 6. GUARDRAILS (from Build Directive)

1. **No rule without scope** — every rule must have domain/task_type/audience/channel/stakes
2. **No promotion from silence** — rules require real application + acceptance (min 3/5)
3. **Aggressive demotion** — misfire penalty -0.25, contradiction penalty -0.20
4. **Correction density is not proof** — never rely on it alone
5. **8.0 quality threshold** — below 8.0 triggers fix cycling (max 3 cycles)
6. **Truth protocol** — no claims without evidence, no banned phrases

---

## 7. DOMAIN AGNOSTIC

The SDK works for ANY domain. The architecture separates:
- **Core tags** (always present): category, session, gate, tone — describe the learning system
- **Domain tags** (configurable): output types, personas, frameworks, channels — describe the business domain

### Domain Configuration

Each brain can include a `taxonomy.json` in its root directory to define domain-specific tag vocabulary. If absent, sales defaults are used (first domain built).

```json
{
  "entity": {"desc": "Primary entity", "mode": "dynamic", "required_on": ["OUTPUT"]},
  "output": {"desc": "Output type", "mode": "closed", "values": ["code_review", "design_doc", "test_plan"]},
  "extra_categories": ["CODE_QUALITY", "PERFORMANCE", "SECURITY"]
}
```

### Supported Intents (default task types)

| Domain | Task Types |
|--------|-----------|
| Generic | meeting_prep, research, content_creation, report_generation, data_analysis, documentation, summary, planning |
| Engineering | code_review, debugging, design_review, refactoring |
| Recruiting | interview_prep, candidate_search, job_description |
| Sales | email_draft, demo_prep, prospecting, objection_handling, follow_up, crm_update |

Custom domains register via `register_task_type(name, keywords, domain_hint)`.
CARL behavioral contracts are per-domain and travel with the brain.

### Entity Abstraction

The SDK uses "entity" as the generic concept for the primary subject of brain knowledge:
- Sales: entity = prospect (brain/prospects/)
- Recruiting: entity = candidate (brain/candidates/)
- Engineering: entity = project (brain/projects/)
- The `prospect:` tag prefix is accepted as an alias for `entity:` in sales brains.

### Domain Coupling Audit (Session 43)

14 files had sales-specific hardcoding. Status after S43 refactor:
- `_tag_taxonomy.py`: **FIXED** — taxonomy loads from brain config, sales is default fallback
- `_events.py`: **FIXED** — dual-write raises on total failure (no silent data loss)
- `patterns/rag.py`: **FIXED** — cascade errors tracked and surfaced in result.mode
- `_events.py`: **FIXED** — start date auto-detected from first event (no hardcoded date), pipeline baseline configurable via `BRAIN_PIPELINE_BASELINE` env var
- `_fact_extractor.py`: **FIXED** — entity directory scans prospects/candidates/customers/entities, fact types loadable from taxonomy.json
- `onboard.py`: **FIXED** — subdirectories are domain-aware (sales→prospects/, recruiting→candidates/, engineering→projects/)
- `brain.py`: **FIXED** — taxonomy reloaded from brain config on Brain init
- **Verified:** Engineering brain with custom taxonomy.json passes all lifecycle checks (code_review output type, SECURITY category, no sales leakage)

### Error Handling Policy (Session 43)

Event emission (the core learning pipeline) must never silently fail:
- Dual-write to JSONL + SQLite; at least one must succeed or RuntimeError raised
- RAG cascade errors tracked in result metadata (no silent `pass`)
- Session detection failures logged to stderr (not silently defaulted)

---

## 8. TECH STACK

```
SDK (what ships):
  Zero required dependencies (pure Python + stdlib)
  Optional: chromadb (vector search), sentence-transformers (local embeddings)
  Optional: google-genai (Gemini embeddings, free tier)
  Storage: SQLite (ships with Python) — one .db file IS the brain

Install:
  pip install aios-brain            # zero deps, works instantly
  pip install aios-brain[memory]    # adds chromadb
  pip install aios-brain[all]       # full stack

Dev:
  uv (build), pytest + hypothesis (testing), pyright (types), ruff + bandit (lint)

Known limitation:
  MCP stdio transport: 0.64 RPS under load (Stacklok testing, 96% failure at 20 connections).
  Real-time correction logging is NOT viable through MCP transport alone.
  Solution: sidecar/watcher.py writes to SQLite out-of-band, independent of MCP channel.
```

---

## 9. PHASED BUILD PLAN (from Revised Vision, updated)

### Phase 1: SDK + MCP Server (current — Sessions 42-60)
**Ship:** Genuinely useful SDK for power users.
**Validation gate:**
- Install on second machine, full lifecycle test
- **PROVE graduation pipeline:** measurably fewer corrections at session 200 vs 50
- 10+ external users
- 3+ users with 50+ sessions showing improvement

### Phase 2: White-Label Agency Revenue
**Ship:** Brain training as a service.
**Validation gate:** $100K revenue from 10 agency clients

### Phase 3: Cloud Dashboard + BYOK
**Ship:** Proprietary scoring runs server-side.
**Validation gate:** 50+ brains, $10K+/month recurring

### Phase 4: Marketplace
**Ship:** Brain listing with quality proof.
**Validation gate:** 100+ renters, <15% monthly churn

### Phase 5: Avengers / A2A Multi-Brain
**Ship:** Composable expert brains via A2A protocol.
**DO NOT BUILD until Phase 4 validates.**

---

## 10. COMPETITIVE MOAT

| Advantage | Strength | Duration |
|-----------|----------|----------|
| Graduation pipeline concept | Medium | 6-12 months (copyable) |
| **Agent-level graduation** | **Strong** | **12-18 months (requires trained agents + data)** |
| Tuned graduation thresholds | Strong | 18-24 months (needs data) |
| Meta-learning across brains | Very Strong | Permanent (data can't be cloned) |
| Domain expertise library | Strong | Permanent (built through agency work) |
| Multi-LLM portability | Medium | Until providers add it |
| Open-source data ownership | Medium-Strong | Enterprise cares deeply |

---

## 11. WHAT'S BUILT (Session 43)

| Component | Status | Files | Lines |
|-----------|--------|-------|-------|
| patterns/ (Layer 0) | 15/15 complete | 15 | ~5,600 |
| enhancements/ (Layer 1) | 16/16 complete | 16 | ~5,400 |
| Core (brain.py, cli.py, mcp_server.py, etc) | Complete | 31 | ~9,500 |
| Tests | 659 passing | 12 | ~7,200 |
| **Total** | **Functional SDK** | **~67** | **~20,600+** |

### What's Done (Session 43)
- [x] 537 tests (9 test files + audit_data_flow.py + test_bug_fixes.py)
- [x] File watcher sidecar (586-line FileWatcher + CLI `aios-brain watch`)
- [x] Wire patterns into Brain class API (14/14 methods + 40+ top-level exports)
- [x] Full MCP server (438-line stdio transport, JSON-RPC 2.0, 37 tests, 5 tools)
- [x] Shim architecture audit (7 thin re-exports, 17 canonical internals, 0 duplicates)
- [x] Second-machine install test (18/18 lifecycle checks in clean venv)
- [x] Gate 0 correction density analysis (GATE0-PROOF.md + scripts/density_graph.py)
- [x] Domain-agnostic taxonomy (`taxonomy.json` config, sales as default)
- [x] Event persistence safety (dual-write raises on total failure)
- [x] All `edited_by_oliver` references removed (domain-agnostic `major_edit` flag)
- [x] End-to-end data flow audit (10 flows verified, DB/JSONL sync confirmed)
- [x] Kill switches by maturity (INFANT=10, ADOLESCENT=7, MATURE=5, STABLE=3 cycles)
- [x] Custom exception hierarchy (BrainError, BrainNotFoundError, EventPersistenceError, etc.)
- [x] Structured logging via `AIOS_BRAIN_LOG=debug` env var
- [x] py.typed marker (PEP 561) + LICENSE file
- [x] Pattern extraction auto-wired into brain.correct()
- [x] examples/quickstart.py for external users
- [x] SDK root cleanup (12 superseded docs archived, stray DB/vectorstore removed)
- [x] correction_rate manifest bug fixed (was always 0.0)
- [x] FACTUAL/CONTENT/TONE/STRUCTURE/STYLE added to core taxonomy
- [x] Agent graduation pipeline (S62): per-agent behavioral profiles, human approval gate graduation (CONFIRM→PREVIEW→AUTO), upward distillation, 27 tests passing
- [x] Statusline gate fix (S62): dedup query, auto-fix for 4 failing checks, 19/19 = 100%
- [x] Path DI (S62): 10 files migrated to env-var pattern (BRAIN_DIR, WORKING_DIR, PYTHON_PATH)
- [x] Hook timeout budget (S62): 3 missing timeouts added, 2 mega-timeouts halved
- [x] Judgment decay algorithm (S62): extracted from brain/scripts to SDK enhancements/
- [x] Rules distillation algorithm (S62): cross-lesson pattern detection extracted to SDK
- [x] Domain coupling fix (S62): reload_config() loads FILE_TYPE_MAP/MEMORY_TYPE_WEIGHTS from taxonomy.json
- [x] Spawn.py migration Wave 1 (S62): route_by_keywords, load_agent_definition, handoff management extracted to SDK. spawn.py now thin shim.
- [x] Scoped agent graduation (S62): agent lessons scoped by task_type, filtered at rule selection
- [x] Wrap-up compacted (S62): 15 phases/21 steps → 10 steps. Codex-verified, /reflect mandatory.
- [x] Full 8-phase audit (S62): AUDIT.md as living North Star reference
- [x] Competitive research (S62): nobody has graduation pipeline. Mem0 48K stars, no behavioral learning.
- [x] Session-type-aware decay (S63): lessons only decay in sessions where their category is testable. DRAFTING immune during system sessions.
- [x] Wave 2 migration (S63): guardrails.py + memory_scope.py pure logic extracted to SDK. 5/7 brain/scripts files migrated.
- [x] Deterministic rule enforcement (S63): RULE-tier patterns compiled to regex guards. DeterministicRule + EnforcementResult + compile_deterministic_rule.
- [x] Architecture review hook (S63): arch-review.js — opinionated PostToolUse on Write/Edit for layer violations, SDK compliance.
- [x] 16 AUDIT gaps closed (S63): I1-I5, I7-I12, I14-I18, I20-I21, I24. From 24 IMPORTANT to 8.
- [x] Tests 605→659 (S63): +54 new tests across decay, guardrails, memory scope, deterministic rules.

### What's Next
- [ ] 10+ external users
- [ ] 3+ users with 50+ sessions showing improvement
- [ ] Statistically significant correction density decrease (need ~200 sessions, at 62)
- [ ] MkDocs documentation setup
- [ ] README rewrite for external developers
- [ ] memory_scope.py migration (Wave 2)

---

## 12. SUPERSEDED DOCUMENTS

This spec replaces:
- `sdk/AIOS_Brain_Build_Directive.md` — Section 3-7 absorbed here
- `sdk/AIOS_Brain_Engineering_Spec.md` — Core modules, data model, build order absorbed here
- `sdk/AIOS-BRAIN-VISION-REVISED.md` — Architecture, phasing, competitive analysis absorbed here
- `sdk/BUILD-ORDER.md` — Wave structure reflected in Section 11
- `sdk/ARCHITECTURE-SPEC.md` — Layer 0/1/2 structure reflected in Section 2

Those files remain as historical context but SPEC.md is the canonical reference.

---

## 13. RESEARCH-BACKED CONSTANTS

Every tunable constant in the SDK has published research justification.

| Constant | Value | Source | Citation |
|----------|-------|--------|----------|
| Loss aversion ratio | 2:1 (-0.20/+0.10) | Meta-analysis of 607 estimates | Brown et al. 2024, Journal of Economic Literature |
| MIN_APPLICATIONS_FOR_PATTERN | 3 | Bayesian posterior > 0.6 after 3 successes | Beta(1,1) prior; NIST Engineering Statistics Handbook |
| MIN_APPLICATIONS_FOR_RULE | 5 | 5-shot learning standard | ACM Computing Surveys 2024 (meta-learning) |
| Blandness threshold (0.70) | Inverted TTR = 0.30 | MTLD segmentation cutoff | McCarthy & Jarvis 2010, JSLHR |
| Quality gate (8.0/10) | 80th percentile | LLM-as-judge calibration | Li et al. 2026, arXiv:2601.03444 |
| Success window (20-25) | CPD minimum segment | Change point detection literature | KAIS 2017 survey |
| MISFIRE_PENALTY (-0.25) | > contradiction | KTO prospect theory alignment | Ethayarajh et al. ICML 2024 |
| EMA update scale (+0.10) | Appropriate for sparse events | EMA decay rates in DL | arXiv:2411.18704 2024 |

Note: LLM-as-judge research (Li et al. 2026) recommends 0-5 scales over 0-10 for better
human-LLM alignment. Future SDK version may switch quality scoring to 0-5.
