# S101 Session Plan — Parallel Execution

**Date:** 2026-04-10
**Budget:** ~$23.50 API cost (DeepSeek + Claude Haiku)
**Baseline:** 1,819 tests passing, main synced with PRs #20-22

## Workstreams

### Wave 1 — All Parallel (start immediately)

#### WT-1: Ship v0.5.0 (Distribution)
- Branch: `release/v0.5.0`
- Fix version mismatch: `__init__.py` 0.2.0 → 0.5.0, `pyproject.toml` 0.4.0 → 0.5.0
- Update CHANGELOG.md with v0.5.0 entry
- Security scan (confirm no secrets in source)
- `uv build` + dry-run publish check
- Tag v0.5.0
- **Does NOT publish to PyPI** — that happens after ablation proves value

#### WT-2: Phase 2 — Scoped Brains API
- Branch: `feat/scoped-brains-api`
- Implement `brain.scope(domain=, task_type=)` → returns scoped view of rules
- Cross-domain meta-rule promotion: detect universal patterns across domains → graduate as UNIVERSAL scope
- Correction-driven scope refinement: "rule fired in wrong domain" → automatic scope tightening
- Tests for all 3 features
- Existing code: `_scope.py` (RuleScope + matching), `rules/scope.py` (TaskType + AudienceTier), `_tag_taxonomy.py`

#### WT-3: Phase 3 — Adapter Verification
- Branch: `fix/adapter-verification`
- Test all 4 adapters (openai, anthropic, langchain, crewai) against current Brain API
- Fix any broken imports/signatures from recent refactors
- Verify `brain.correct()`, `brain.apply_brain_rules()`, `brain.prove()` work as thin core API
- Verify MCP server end-to-end
- Existing code: `integrations/` (4 adapters), `context_wrapper.py`, `mcp_server.py`

#### WT-4: Phase 7 — Integration Test Gaps
- Branch: `test/integration-gaps`
- Atomic file write tests (race conditions, lock scenarios)
- API failure mode tests (timeout, retry, graceful degradation)
- Cascading correction tests (correction of a correction)
- Encryption at-rest tests (optional cryptography dependency)
- Existing: 1,819 unit tests, integration tests for all 4 adapters

#### WT-5: Ablation Baseline ($10)
- Script: `brain/scripts/ablation_experiment.py`
- Three-way comparison: Bare LLM (A) vs CLAUDE.md config (B) vs Brain rules (C)
- 200 tasks across 5 domains (email 50, code 40, planning 40, sales 40, docs 30)
- Task source: mine events.jsonl for real correction contexts + synthetic supplement
- 3 conditions × 5 runs per condition = 3,000 generations (DeepSeek V3)
- 3,000 blind judge evaluations (Claude Haiku — cross-model, no self-eval bias)
- 5 scoring dimensions: accuracy, voice, structure, conciseness, judgment (1-10)
- CLAUDE.md baseline: curated fair "best-effort static config" from Oliver's known preferences
- Success: C wins >70% vs A (strong signal), C wins >55% vs B (rules beat config)
- Output: `brain/stress_test_results/ablation/baseline_report.json`

#### MiroFish: 3 Meta-Rule Sims ($3.50)
- Script: `brain/scripts/mirofish_sim_v2.py` (extend with new sim definitions)
- All sims: 50 agents × 10 steps × 3 rounds = 1,500 calls each

**Sim A: Blind Discovery** (all agents neutral)
- 10 expert personas discover meta-rule taxonomy from scratch
- No priming with existing categories
- Goal: what categories emerge organically? Compare to Tone/Structure/Precision

**Sim B: Audit Existing** (mix supportive + hostile)
- Same 10 personas stress-test current Tone/Structure/Precision taxonomy
- Goal: find gaps, overlaps, blind spots, edge cases

**Sim C: Pattern Detection Red Team** (majority hostile/skeptical)
- Show actual algorithm code (rule_engine.py, _scope.py, FSRS confidence)
- Goal: find blind spots in pattern detection and matching

#### BG-1: Open Source Scenario Research
- Research agent (web search + precedent analysis, no LLM API cost)
- 7 scenarios: competitor copies, Anthropic builds native, community fork, enterprise AGPL ban, OSS accelerates adoption, nobody cares, delayed open source
- Precedents: Redis, Elastic, MongoDB, Sentry, Supabase, io.js
- Output: decision document with timeline scenarios at 1/6/12/24 months

#### MAIN: Supabase Migration
- Run `cloud/migrations/001_initial_schema.sql` against live Supabase (ref: miqwilxheuxwafvmoajs)
- Provision DB for cloud sync

### Wave 2 — After MiroFish (~15 min)

#### Synthesize MiroFish Findings
- Extract consensus: missing categories, taxonomy gaps, pattern detection blind spots
- Identify formula structural changes recommended by expert panel

#### Fix Formula
- Apply MiroFish-recommended structural changes to compound score
- Update `_manifest_quality.py` and related scoring code

#### Autoresearch: Weight Optimization
- No LLM cost — pure math on existing 29-brain stress test data
- Perturb weights, re-score all brains, optimize for correlation with real learning
- Output: optimized weight vector

### Wave 3 — After Wave 2 (~10 min)

#### Ablation v2: Improved System ($10)
- Same experiment as baseline but with improved formula/weights
- Compare to baseline ablation: did MiroFish improvements help?
- Output: `brain/stress_test_results/ablation/improved_report.json`

## Out of Scope
- Dashboard frontend (separate session, needs full brainstorm)
- Website email capture (marketing, not SDK)
- Making repo public (after ablation proves value)
- npm publish (MCP server is Python)
- Mem0 adapter (no Mem0 SDK to test locally)

## Dependencies
```
Wave 1 (parallel):
  WT-1 ─────────────────────────────────────── → PR ready
  WT-2 ─────────────────────────────────────── → PR ready
  WT-3 ─────────────────────────────────────── → PR ready
  WT-4 ─────────────────────────────────────── → PR ready
  Ablation baseline ─────────────────────────── → baseline_report.json
  MiroFish (3 sims) ──┐
  OSS research ────────│───────────────────── → decision doc
  Supabase migration ──│───────────────────── → DB provisioned
                       │
Wave 2 (sequential):   ▼
  Synthesize MiroFish → Fix formula → Autoresearch weights

Wave 3 (sequential):
  Ablation v2 (improved) ───────────────────── → improved_report.json
```

## Prerequisites
- DEEPSEEK_API_KEY set in environment
- ANTHROPIC_API_KEY set in environment (for Haiku judge)
