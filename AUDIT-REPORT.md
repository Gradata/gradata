# Gradata Learning Engine — Full System Audit Report

**Date:** 2026-03-27 | **Session:** S75 (system)
**Test baseline:** 973 passing (450 SDK + 523 cloud), 23 skipped, 0 failures

---

## Track 1: Data Integrity Audit

### Correction Events
- **Total corrections:** 60
- **ALL corrections sourced from `backfill:session_notes`** — zero from live `capture_learning.py`
- **ALL corrections have `severity: None`** — edit distance never computed on backfill data
- Sessions with corrections: S3, S4, S5(8), S6(4), S15(4), S18, S20, plus later sessions

### Density Anomalies (3 found)

| Session | Density | Outputs | Corrections | Bug |
|---------|---------|---------|-------------|-----|
| S35 | 0.0 | 0 | 2 | Density should be >0 (corrections exist) or outputs should be >0 |
| S36 | 0.8 | 0 | 0 | Density=0.8 with zero events — phantom data |
| S69 | 0.0 | 70 | 5 | Density should be 5/70=0.071, not 0.0 |

### Session Metrics Gaps
- S54-S58, S65-S66, S73: `outputs_produced=0` — sessions either not tracked or too short
- S64, S67, S68: corrections>0 but `correction_density=None` — not computed at wrap-up
- S72, S74: no session_metrics row at all despite having events

### Classification Quality
- `capture_learning.py` has 14 categories with keyword-based classification
- First-match-wins strategy means order-dependent bugs are possible
- No "GENERAL" fallback category — unmatched prompts are silently dropped
- **MAX_CAPTURE_PROMPT_LENGTH=2000 bytes** — may truncate long corrections

### Verdict: FAIL — backfill-only data, severity never computed, 3 density anomalies

---

## Track 2: Graduation Logic Proof

### Pipeline Status

| Step | Module | Status |
|------|--------|--------|
| Correction capture | `capture_learning.py` | WORKING (hooks fire) |
| Lesson creation | `_self_improvement.py` shim | BROKEN locally — stubs return [] |
| Edit classification | `_edit_classifier.py` shim | BROKEN locally — stubs return [] |
| Pattern extraction | `_pattern_extractor.py` shim | BROKEN locally — stubs return [] |
| Confidence scoring | `_self_improvement.py` shim | BROKEN locally — returns 0.0 |
| Graduation | `_self_improvement.py` shim | BROKEN locally — returns [] |
| Rule engine | `patterns/rule_engine.py` | WORKING (687 lines, fully implemented) |
| Rule injection | `format_rules_for_prompt()` | WORKING (XML tags, primacy/recency) |
| Meta-rule discovery | `enhancements/meta_rules.py` | PARTIAL — classes defined, discovery algorithm missing |

### Missing Files (Ship Blockers)
These files are referenced by shims but DO NOT EXIST in `enhancements/`:
1. `enhancements/self_improvement.py` — graduation, confidence, parsing
2. `enhancements/edit_classifier.py` — edit classification
3. `enhancements/pattern_extractor.py` — pattern extraction

### Cloud Backup Has Them
- `gradata_cloud_backup/graduation/` has working graduation logic (523 tests pass)
- But open-source users get dead stubs

### Session-Type Decay (CATEGORY_SESSION_MAP)
- Cannot verify — `update_confidence()` is a stub locally
- Cloud backup implementation exists but needs separate audit

### Graduation Timeline Modeling
With penalty=-0.18 (major), survival=+0.08 (flat), threshold=0.90:
- Best case (zero corrections): 0.30 + (8 sessions * 0.08) = 0.94 → **~8 sessions to RULE**
- Realistic (1 major correction every 5 sessions): 0.30 + 5*0.08 - 0.18 + 5*0.08 - 0.18 ... → **~15-20 sessions**
- Worst case (frequent corrections): lesson stuck at INSTINCT indefinitely ✓

### Verdict: FAIL — open-source graduation pipeline is completely non-functional

---

## Track 3: MCP Tool Binding

### Current State
- `brain.correct()` accepts `draft` and `final` parameters
- Edit distance computed from real text diffs via `diff_engine.py` (compression + Levenshtein)
- Severity is computed, NOT user-supplied ✓

### Missing Validations
1. **No draft===final rejection** — brain.correct("hello", "hello") silently emits a no-op CORRECTION
2. **No empty string rejection** — brain.correct("", "") emits an event
3. **No rate limiting** — unlimited corrections per session possible
4. **No session fabrication prevention** — `session` parameter is user-supplied, not validated
5. **No MCP-specific entry point** — brain.correct() is the same API for MCP and local use

### Positive
- Edit distance IS computed from real text, not user-declared severity ✓
- Dual-write ensures events are persisted reliably ✓
- Event schema includes source attribution ✓

### Verdict: PARTIAL — real diff computation works, but missing input validation

---

## Track 4: Quality Metrics Pipeline

### brain.manifest() Output (from brain.manifest.json)
```
correction_rate: 0.143
lessons_graduated: 63
lessons_active: 39
first_draft_acceptance: 0.0
sessions_trained: 44
```

### Issues
1. **`first_draft_acceptance: 0.0`** — either broken metric or every output was edited (unlikely for 1,056 outputs)
2. **`correction_rate: 0.143`** — this is corrections/outputs = 60/~420 ≈ 0.143. Plausible but based on backfill data
3. **`compound_score` not present** in manifest — referenced in CLAUDE.md but not generated
4. **`categories_extinct` not present** in manifest — referenced but not generated
5. No external signal integration (email reply rates, calendar bookings, deal progression)
6. No "proof of improvement" artifact template exists

### Dashboard
- `learning_dashboard.py` exists and queries correct tables
- Metrics: FDA, correction density, severity trends, lesson applications
- But underlying data is backfill-only (Track 1 findings)

### Verdict: PARTIAL — manifest generates but missing key metrics, FDA broken

---

## Track 5: Hook Verification

### Dispatcher Inventory

| Dispatcher | Hooks Referenced | Actually Execute |
|------------|-----------------|------------------|
| session-start | 3 | Needs verification |
| post-tool | 14 | Needs verification |
| pre-tool | 6 | Working (blocking gates active) |
| user-prompt | 7 | capture_learning.py fires |
| stop | 4 | Working |
| pre-compact | 2 | Working |

### Critical Git Status Issue
**50+ hook files marked DELETED in git index but present on disk.** This means:
- Runtime: hooks work (files exist on disk)
- Git: next commit/push will drop these files
- Impact: ALL hooks would be deleted from repo if committed

### Orphan Hooks
3 files in `orphan/` directory: gemini-research.js, model-router.js, research-synthesizer.js
- Not called by any dispatcher
- Should be reviewed for deletion or re-integration

### behavior-triggers.js (Rule 14: Plan-First Gate)
- Uses `/tmp/gradata-behavior-state.json` — Windows path issue
- Session collision risk if multiple terminals use same temp file

### Verdict: PARTIAL — dispatchers correctly reference files, but git status is corrupted

---

## Track 6: Evolution Rules Audit

### Meta-Rule Discovery (`enhancements/meta_rules.py` — 1,614 lines)
- **Classes defined:** MetaRule, SuperMetaRule (Rosch 3-tier)
- **Condition evaluation:** `evaluate_conditions()` works
- **Discovery algorithm:** NOT IMPLEMENTED — no `discover_meta_rules()` function found
- **Database table:** `meta_rules` exists in system.db but empty

### Rule Verifier (`enhancements/rule_verifier.py` — 276 lines)
- Pre-execution filtering by tool type ✓
- Post-hoc regex checks (em dash, pricing, calendly) ✓
- Database persistence of verification results ✓
- **Limitation:** regex-only, no semantic understanding

### Ablation Framework (`enhancements/rule_canary.py` — 276 lines)
- A/B testing infrastructure exists ✓
- **BLOCKER:** 4 hardcoded paths to `C:/Users/olive/SpritesWork/brain/`
- Safety blocklist: not explicitly found but canary has test window constraints

### Bonus Rule Pattern
- No mechanism for agent-discovered gaps to become rules
- `brain.detect_implicit_feedback()` captures signals but doesn't create lessons
- Gap: implicit feedback → lesson creation pipeline missing

### Agent-to-Brain Feedback
- No upward distillation from sub-agents to brain in open-source SDK
- Cloud backup has `agent_graduation.py` but it's proprietary

### Verdict: PARTIAL — infrastructure exists, discovery algorithm and agent feedback missing

---

## Track 7: Cross-Brain Isolation & Multi-Tenancy

### Namespace Isolation
- `BrainContext` DI container holds per-instance paths ✓
- Each Brain instance operates on its own `brain_dir` ✓
- Events dual-write to brain-local JSONL + SQLite ✓
- **Risk:** `_paths.py` has module-level globals for backward compat — concurrent brains in same process could collide

### Session Numbering
- `_detect_session()` infers session from context or increments global counter
- **Risk:** Two brains in same process share the global counter → session ID collision
- Production mitigation: each brain has separate SQLite, so IDs are brain-local

### Data at Rest
- Each brain's SQLite is fully isolated (separate file) ✓
- Events.jsonl is brain-local ✓
- No shared state between brain instances at rest ✓

### Verdict: PASS (with caveats) — isolation works for separate processes, risky for in-process multi-brain

---

## Track 8: Decay & Retirement

### Session-Type-Aware Decay
- `CATEGORY_SESSION_MAP` referenced in memory (built S63)
- Cannot verify locally — `update_confidence()` is a stub
- Cloud backup likely implements this

### Untestable Lesson Detection
- `UNTESTABLE_SESSION_LIMIT = 20` defined in constants
- `LessonState.UNTESTABLE` and `KILLED` states exist in type system ✓
- State transitions defined: UNTESTABLE → promote(INSTINCT) or kill(KILLED) ✓
- **Gap:** No code found that actually scans lessons for 20+ session inactivity

### Rule Retirement (Demotion)
- State machine allows: RULE → demote → PATTERN ✓
- PATTERN → demote → INSTINCT ✓
- **Gap:** No automated demotion trigger found — only manual via `transition()`

### Staleness Sweep
- `lessons-archive.md` exists for ARCHIVED lessons
- No automated sweep found that moves stale lessons to archive
- Lessons accumulate indefinitely in `lessons.md`

### Verdict: FAIL — decay logic defined but not automated

---

## Track 9: Correction Detection Accuracy

### False Positive Risk
- `r"\b(actually|instead|rather)[,.]?\s"` at confidence 0.65 — "actually" fires on normal conversation
- `r"\b(but|however)[,.]?\s+(the|this|that)"` at confidence 0.55 — common in non-correction text
- `r"hallucin"` in capture_learning.py — matches "hallucination" but also any word containing substring

### False Negative Risk
- Multi-turn corrections: "no" on turn 1, "I mean X" on turn 2 — **detector is single-turn only**
- Corrections via action (user just edits and resubmits without explicit signal) — undetected
- **All 60 corrections in system.db are backfill, not live-detected** — live detection untested in production

### MAX_PROMPT_LENGTH=2000
- Real prompts can exceed 2000 bytes easily (code snippets, long context)
- Exception for "remember:" marker — good
- Should profile real prompt lengths to validate

### Verdict: FAIL — untested in production, known false positive patterns, single-turn only

---

## Track 10: SDK Public API Surface

### Current Exports: 48 symbols in `__all__`
**Should be ~5 for launch:**
1. `Brain` — main class
2. `BrainContext` — DI container
3. `Lesson` — data class (for type hints)
4. `LessonState` — enum (for type hints)
5. `__version__`

### Pattern Exports (43 symbols — too many)
Pipeline, Stage, GateResult, PipelineResult, ParallelBatch, ParallelTask, DependencyGraph,
merge_results, EpisodicMemory, SemanticMemory, ProceduralMemory, MemoryManager, InputGuard,
OutputGuard, Guard, GuardCheck, MCPBridge, MCPToolSchema, MCPServer, assess_risk,
RiskAssessment, HumanLoopGate, CritiqueChecklist, Criterion, reflect, EMAIL_CHECKLIST,
EvalDimension, evaluate_optimize_loop, AudienceTier, TaskType, classify_scope, Delegation,
DelegationResult, orchestrate, SmartRAG, NaiveRAG, RuleApplication, onboard,
compute_learning_velocity, format_lessons, graduate, parse_lessons, update_confidence,
RuleTransferScope

### Brain.init() Fresh Machine Test
- Calls `onboard.onboard()` which creates directory structure
- Works without brain vault ✓
- Auto-detects interactive terminal ✓
- **Risk:** If BRAIN_DIR env not set and gradata_cloud not available, some features silently fail

### brain.correct() Return Value
- Returns event dict with diff, classifications, patterns
- **But:** classifications=[] and patterns=[] locally (stubs)
- Missing: severity, category, confidence in return value

### brain.search() Quality
- FTS5 keyword search only — no semantic ranking
- Returns source, text, score, confidence
- Adequate for v0.1.0 but weak compared to vector search

### Error Messages
- `BrainNotFoundError` — developer-friendly ✓
- `EventPersistenceError` — clear ✓
- Cloud connection failures silently swallowed — developer-unfriendly

### Verdict: FAIL — API surface too large (48 vs 5), core methods return empty data locally

---

## Track 11: Event Schema Consistency

### Event Types Found in system.db
CORRECTION, OUTPUT, HUMAN_JUDGMENT, DELTA_TAG, AUDIT_SCORE, HEALTH_CHECK,
SESSION_END, STEP_COMPLETE, GATE_RESULT, LESSON_CHANGE, IMPLICIT_FEEDBACK,
FACT_EXTRACTED, FACT_UPDATED, FACT_INVALIDATED, RULE_APPLICATION,
SENTIMENT_TAG, CONTRADICTION_DETECTED, CONSOLIDATION_SCAN (22 total per manifest)

### Schema Compliance

| Field | Expected | Actual |
|-------|----------|--------|
| ts | ISO datetime | ✓ all events |
| session | int | ✓ all events |
| type | string | ✓ all events |
| source | string | ✓ but varies ("backfill:session_notes" vs "brain.correct" vs "hook:capture_learning") |
| data | dict | ✓ all events (but nested structure varies by type) |
| tags | list[str] | ✓ most events (some have empty list) |
| valid_from | ISO datetime | ✓ (defaults to ts) |
| valid_until | string/null | ✓ |

### Consumer Consistency
- `wrap_up.py` reads `data_json` from SQLite — correct ✓
- `learning_dashboard.py` reads `data_json` — correct ✓
- `correction_severity` reads from events table — correct ✓
- **Risk:** Some consumers read `data["category"]` directly, others read `json_extract(data_json, '$.category')` — same data, different access patterns

### Verdict: PASS — schema is consistent, minor source attribution variance

---

## Track 12: Security Pre-Launch

### Secrets in SDK Source
- **4 hardcoded paths** in `rule_canary.py`: `C:/Users/olive/SpritesWork/brain/`
- No API keys, tokens, or credentials in source ✓
- `GRADATA_API_KEY` read from env var only ✓

### License Headers
- AGPL-3.0 license file present ✓
- No per-file headers (not required for AGPL, but recommended)

### Brain Vault Data
- `events.jsonl`, `system.db`, `prospects/` NOT in SDK repo ✓
- Brain vault at separate path (`C:/Users/olive/SpritesWork/brain/`) ✓

### Sprites.ai References
- `rule_engine.py`: "sprites" in `_TEAM_SIGNALS` list — tool keyword, not brand reference
- `meta_rules.py`: "Oliver" in example comments — personal reference in SDK code
- Should be genericized before public release

### Dependencies
- Zero required dependencies ✓
- Optional: sentence-transformers, google-genai
- Dev: pytest, hypothesis, pyright, bandit, coverage
- No known CVEs in optional deps

### Deprecated Files
- `.vectorstore/chroma.sqlite3` (188KB) still in SDK — ChromaDB deprecated, should be removed

### Verdict: PARTIAL — 4 hardcoded paths + personal references need cleanup

---

## Track 13: Benchmark Reproducibility

### Clone → Install → Run Test
```bash
git clone <repo>
cd gradata
pip install -e ".[dev]"
pytest sdk/tests/  # 450 pass, 23 skip
```
- Works ✓ (tested)
- `Brain.init()` works without brain vault ✓
- Test fixtures use `tmp_path` — self-contained ✓

### CLB (Correction Learning Benchmark) from Zero
- Not yet defined as a standalone benchmark
- Would need: synthetic corrections, expected graduation timeline, assertion on final state
- **Gap:** No CLB exists yet

### Verdict: PARTIAL — basic test flow works, CLB benchmark not yet built

---

## Summary Scorecard

| Track | Score | Status |
|-------|-------|--------|
| 1. Data Integrity | 3/10 | FAIL — backfill only, severity=None, 3 anomalies |
| 2. Graduation Logic | 2/10 | FAIL — 3 missing modules, stubs return empty |
| 3. MCP Tool Binding | 5/10 | PARTIAL — diff works, no input validation |
| 4. Quality Metrics | 4/10 | PARTIAL — manifest generates, key metrics missing |
| 5. Hook Verification | 6/10 | PARTIAL — dispatchers correct, git corrupted |
| 6. Evolution Rules | 4/10 | PARTIAL — infrastructure exists, discovery missing |
| 7. Cross-Brain Isolation | 7/10 | PASS — isolated at rest, risky in-process |
| 8. Decay & Retirement | 3/10 | FAIL — logic defined, not automated |
| 9. Correction Detection | 3/10 | FAIL — untested live, false positives |
| 10. SDK API Surface | 4/10 | FAIL — 48 exports, core returns empty |
| 11. Event Schema | 8/10 | PASS — consistent schema |
| 12. Security | 6/10 | PARTIAL — 4 hardcoded paths |
| 13. Benchmark | 5/10 | PARTIAL — tests work, no CLB |

**Overall: 4.6/10 — Not launch-ready. Critical gaps in graduation pipeline and data integrity.**

---

## Future Architecture Considerations

### The Fundamental Tension
The SDK is designed as open-source + proprietary cloud, but the open-source layer is non-functional
for core learning. This is the #1 ship blocker. Two paths:

**Option A: Port graduation to open-source**
- Move `self_improvement.py`, `edit_classifier.py`, `pattern_extractor.py` from cloud to SDK
- Pros: SDK works standalone, builds trust, enables community testing
- Cons: Proprietary logic exposed, reduced cloud differentiation

**Option B: Require cloud connection for learning**
- SDK captures corrections locally, syncs to cloud for graduation
- Pros: Protects secret sauce, simpler SDK
- Cons: SDK useless offline, higher barrier to adoption, anti-open-source optics

**Recommendation: Option A** — port basic graduation logic to open-source.
Keep advanced features (multi-brain optimization, marketplace scoring) cloud-only.
Basic INSTINCT→PATTERN→RULE with confidence math is not the moat.
The moat is data volume, quality proof, and marketplace network effects.

### Multi-Brain Scaling (S73+ Vision)
- Current: single Brain per process works
- Needed: 10 simulated personas validating multi-brain
- Challenge: corrections encode human judgment — can't be synthesized
- Approach: use CLB with synthetic corrections as proxy, then real user testing

### Agent-to-Brain Feedback Loop
- Sub-agents discover patterns (gaps, not corrections)
- These should enter as INSTINCT lessons with source="agent:gap_discovery"
- Lower initial confidence (0.15 vs 0.30) since not human-validated
- Graduation requires human confirmation to reach PATTERN

### Marketplace Readiness
- brain.manifest.json is the proof artifact — schema exists ✓
- Missing: compound_score, improvement_curve, external_signal_correlation
- Launch with manifest v1.0, iterate based on early user feedback
