# Gradata Leanout Plan (Phase C)

Source: claude-opus-4-7 ran the lean-out audit overnight (2026-04-30 ~02:12). The agent prepared the plan but couldn't `Write` the file directly (permission gate). Plan extracted from stdout for posterity.

## Baseline (measured)

- **SDK:** 68,717 LOC across 249 files (`src/gradata/`)
- **Tests:** 49,984 LOC across 192 files (`tests/`)
- **Total repo LOC (council count):** 176k including docs/scripts/examples

Target after lean-out: ≈ 43,861 SDK LOC (-36 %), reaching 40 % goal after deferred deletions in v0.8.

## Council finding #1 — Scoring schemes (pick ONE)

| File | LOC | Verdict | Reason |
|---|---|---|---|
| `enhancements/self_improvement/_confidence.py` | — | **CANONICAL — KEEP** | FSRS-inspired severity-weighted Bayesian. 32 call-sites across SDK. Most defended. |
| `enhancements/graduation/scoring.py` | 203 | **REMOVE** | Opt-in alt-path, no unique callers. |
| `enhancements/scoring/memory_extraction.py` | 329 | **REMOVE** | Broken import path. |
| `enhancements/scoring/*` (rest) | ~3,645 | **MOVE → `gradata[observability]` extra** | Useful for debugging, not kernel. |

Pragmatist disagrees: prefers Beta (simplest defensible math) over Bayesian/FSRS — flag for Oliver's call.

## Council finding #2 — Duplicate-purpose modules

Architect's audit reveals only ONE pair is a true duplicate:

| Pair | Verdict |
|---|---|
| `inspection.py` vs `brain_inspection.py` | **DUPLICATE** — fold mixin into `Brain` (-168 LOC) |
| `events_bus.py` vs `_events.py` | NOT duplicate — confusingly named. **Rename** `events_bus.py → _subscribers.py` |
| `_config.py` vs `_config_paths.py` | NOT duplicate. **Rename** `_config.py → _rag_config.py` |

## Council finding #3 — Correction APIs (pick ONE canonical)

| API | Verdict |
|---|---|
| `Brain.correct()` | **CANONICAL — KEEP as the only public entry** |
| `Brain.record_correction` | Make private: `_record_correction` |
| `Brain.log_output` | Rename: `observe()` (it's not a correction — it's an observation) |
| `correction_detector.py` | Make private: `_correction_detector.py` |
| `enhancements/graduation/agent_graduation.py` | 901 LOC → MOVE to `gradata[agents]` extra |

## Council finding #4 — Cloud sync (off the main path)

| File | LOC | Verdict |
|---|---|---|
| `_cloud_sync.py` | 541 | **REMOVE** (dead MVP — lots of recent fix commits, never stable) |
| `cloud/*` | 402 | **MOVE → `gradata[cloud]` extra** |

Architect goes harder: "delete, don't deprecate." Pragmatist agrees: "kill, not 'later'."

## Other surface to move behind extras

- `mcp_server.py` + `mcp_tools.py` → `gradata[mcp]`
- `daemon.py` → questionable; pragmatist says **DELETE entirely** (MCP server covers the integration use case)
- `contrib/patterns/*` → `gradata[patterns]`
- `adapters/*` (mem0 adapter) → `gradata[adapters-mem0]` (already extra)
- `_mine_transcripts.py` → `gradata[mining]`
- `sidecar/` → `gradata[sidecar]`
- `detection/` → re-evaluate; some belongs in kernel, most doesn't
- 22 of 30 `hooks/*` scripts → `gradata[hooks]`

## Kernel after lean-out

The minimum-viable v1.0 surface:

- `brain.py` (Brain class)
- `correct()` (the only public correction API)
- `apply_brain_rules()` (recall)
- `search()` (FTS)
- `manifest()` (quality proof)
- `_atomic.py` (already added by Phase B)
- `_brain_lock.py` (already added by Phase B)
- `rules/rule_graph.py` (atomic now)
- `_events.py` (single sink)
- `_db.py`, `_paths.py`, `_types.py` (Layer 0 primitives)
- `_doctor.py` (CLI health check)
- `cli.py` (entry point)
- `exceptions.py`
- ONE scoring scheme (`_confidence.py`)
- One inspection module (folded into Brain)

Estimated kernel LOC: 35–45k.

## 16-Step PR-by-PR execution order (claude-opus draft)

The full ordered list lives in the claude stdout dump. Headlines:

1. Single mass-deletion PR (cloud_sync, daemon, agent_graduation, 3 confidence schemes, duplicates) — ~40% LOC gone in one commit
2. Deterministic core-loop test (PMR-100 / correction-retention-@N benchmark)
3. Collapse to single `correct()` API, others made private
4. Atomic writes + process lock (DONE in Phase B commit 242c408d)
5. README rewrite — one paragraph, one code example, one benchmark table
6. Move cloud/MCP/patterns/adapters/mining/sidecar to extras
7. Rename non-duplicate modules
8. Fold inspection mixin into Brain
9. Update CLAUDE.md / AGENTS.md to match new surface
10. Pin Python ≥3.11
11. ruff/pyright pass
12. Test isolation audit
13. Docs cull (delete aspirational)
14. examples/ → 1 minimal example
15. Tag v1.0.0-rc1
16. Show HN with PMR-100 chart vs Mem0 LOC comparison

## 6 audits to do BEFORE Phase D

- `_validator.py` — is this dead?
- `_manifest_helpers.py` / `_manifest_metrics.py` / `_manifest_quality.py` — three files, do they need to be three?
- `enhancements/scoring/{calibration,gate_calibration,brain_scores,correction_tracking}.py` — borderline
- `_data_flow_audit.py` — keep or kill?
- `enhancements/clustering.py` + `cluster_manager.py` + `meta_rules*.py` — entangled, separate audit needed
- `integrations/` (deprecated, scheduled for v0.8) — confirm migration path complete

## Pragmatist's correction (disagreement flagged in council)

Pragmatist says **60 days**, not 90. "30 days is malpractice. 90 is the solo-founder graveyard."

Pragmatist's KILL list is more aggressive than architect's MOVE list — recommends deleting from main rather than gating behind extras for: `notifications.py`, `onboard.py`, `safety.py`, `agent_graduation.py`, `correction_detector.py`, `implicit_feedback`.

User to decide: aggressive delete (pragmatist) vs gentler move-behind-extras (architect).

## Confidence flags (honest)

- **HIGH:** the four council findings — every working lens converged.
- **MED:** "delete vs move behind extra" depends on whether you ever expect users to need cloud / agent-graduation. Pragmatist read: never. Architect read: someday.
- **MED:** scoring scheme winner. Architect picked Bayesian/FSRS. Pragmatist picked Beta. No clear data — needs a benchmark to settle.
- **UNAVAILABLE:** Wildcard lens failed (deepseek-v4-pro:cloud 500 error). 6 of 7 voices in synthesis.
