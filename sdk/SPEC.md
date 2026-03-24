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

The brain is portable (one SQLite file), verifiable (quality scores from real data), and domain-specific (trained over hundreds of sessions).

### The Graduation Pipeline (core innovation)

```
INSTINCT (0.0-0.59) → PATTERN (0.60-0.89) → RULE (0.90+)

Promotion requires:
  - Real application (min 3 for PATTERN, min 5 for RULE)
  - No promotion from silence
  - Aggressive demotion on misfire (-0.25)
  - Scoped per domain/task_type/audience/channel/stakes

Kill switches by maturity:
  INFANT (0-50 sessions): 10 cycles zero value
  ADOLESCENT (50-100): 7 cycles
  MATURE (100-200): 5 cycles
  STABLE (200+): 3 cycles
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
| RAG | rag.py | Cascade: FTS→Vector→Hybrid, graduation-aware scoring |
| Rule Engine | rule_engine.py | Scope-aware rule selection + prompt injection |
| Rule Tracker | rule_tracker.py | RULE_APPLICATION event logging |
| Tools | tools.py | Tool registry + plan-before-execute |
| MCP | mcp.py | Brain-to-host protocol bridge |

### Layer 1: Enhancements (13 modules)
| Enhancement | Module | Purpose |
|-------------|--------|---------|
| Self-Improvement | self_improvement.py | INSTINCT→PATTERN→RULE graduation |
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

### Layer 2: Trained Brain (user's data)
```
brain/
  system.db              — SQLite: events table (event-sourced, all data)
  events.jsonl           — Append-only portable event log
  brain.manifest.json    — Quality + capability declaration
  prospects/             — Semantic memory (domain entities)
  sessions/              — Episodic memory (session notes)
  emails/PATTERNS.md     — Procedural memory (what works)
```

---

## 3. CORE LOOP (from Engineering Spec)

```
User Prompt
  → AI Draft (brain.log_output)
  → User Edits / Corrections
  → Final Output
  → Diff Engine (compute_diff)
  → Edit Classifier (classify_edits)
  → Pattern Extraction (extract_patterns)
  → Scoped Graduation (update_confidence)
  → Rule Application (apply_rules)
  → Metrics Update (compute_metrics)
```

Entry point: `brain.correct(draft, final)` — captures the full loop.
Rule injection: `brain.apply_brain_rules(task, context)` — returns formatted rules.

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
- Output becomes bland → regression to mean

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

The SDK works for ANY domain. Current supported intents:

| Domain | Task Types |
|--------|-----------|
| Generic | meeting_prep, research, content_creation, report_generation, data_analysis, documentation, summary, planning |
| Engineering | code_review, debugging, design_review, refactoring |
| Recruiting | interview_prep, candidate_search, job_description |
| Sales | email_draft, demo_prep, prospecting, objection_handling, follow_up, crm_update |

Custom domains register via `register_task_type(name, keywords, domain_hint)`.
CARL behavioral contracts are per-domain and travel with the brain.

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
| Tuned graduation thresholds | Strong | 18-24 months (needs data) |
| Meta-learning across brains | Very Strong | Permanent (data can't be cloned) |
| Domain expertise library | Strong | Permanent (built through agency work) |
| Multi-LLM portability | Medium | Until providers add it |
| Open-source data ownership | Medium-Strong | Enterprise cares deeply |

---

## 11. WHAT'S BUILT (Session 42)

| Component | Status | Files | Lines |
|-----------|--------|-------|-------|
| patterns/ (Layer 0) | 15/15 complete | 15 | ~5,000 |
| enhancements/ (Layer 1) | 13/13 complete | 13 | ~4,500 |
| Core (brain.py, cli.py, etc) | Complete | 30 | ~9,000 |
| Tests | 32 passing | 2 | ~600 |
| **Total** | **Functional SDK** | **60** | **~18,800** |

### What's Next
- [ ] 120+ tests (patterns + enhancements)
- [ ] Wire patterns into Brain class API
- [ ] Clean up backward-compat shims
- [ ] Full MCP server (transport layer)
- [ ] File watcher sidecar (observation capture)
- [ ] Second-machine install test
- [ ] Graph correction density over 200 sessions (Gate 0 proof)

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
