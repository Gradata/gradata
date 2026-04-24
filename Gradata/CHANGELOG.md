# Changelog

## [Unreleased] — post-0.6.0 (2026-04-23 → 2026-04-24)

33 commits ahead of public `origin/main`. Not yet pushed.

### Added

- **Cloud sync + Supabase schema hardening.** Dual-write path now pushes local
  brain events to Supabase with a transform layer (`_cloud_sync.py`) that maps
  SQLite rows to cloud schema + scrubs JSONB payloads. Watermark-based
  incremental sync via `sync_state` table (migration 003).
- **Local SQLite migrations 002 + 003.** `002_event_id_device_id_content_hash`
  adds sync-stable identifiers; `003_add_sync_state` creates the watermark table.
  Both idempotent — `CREATE TABLE IF NOT EXISTS` + `add_column_if_missing` + `has_applied()` gating.
- **Supabase migrations 014/015/016 applied to prod.** UNIQUE constraints on
  `corrections(brain_id, session, description)` and `events(brain_id, type, created_at)`,
  plus `brains.last_used_at` column. Reference SQL tracked under
  `Gradata/migrations/supabase/`; README documents application state + governance.
- **Canonical graduation + persistent brain_prompt + two-provider synth**
  (`f91d5557`). `<brain-wisdom>` now regenerates on every graduation-triggering
  session close, model-agnostic.
- **Context-window watchdog hook** (`ctx_watchdog`, commit `56bac80c`): auto-handoff
  when Claude Code context hits threshold. Reduces forced /clear losses.
- **Auto-compact handoff pipeline** (`485cd7b4`): two-phase /clear injection so
  session state survives compaction.
- **Code-review-graph activation enforced** before any Glob/Grep call
  (`fd956ec4`) — pushes agents to use the structural graph instead of brute-force
  file search.
- **Cloud-health probes in `gradata doctor`** (`d5425337`): reachability + auth
  token validation + data sanity.
- **`lesson_applications` audit loop** (`d668bab7`): closes the
  compound-quality feedback cycle.
- **Implicit feedback: text-speak detection** (`5a6da455`, `1a497e85`):
  catches corrections phrased as "r/u/dont/cant".

### Changed

- **Statusline session count** sourced from Anthropic JSONL (`18166663`,
  `74af66e6`, `a405447d`) — replaces stale `loop-state.md` counter (367 → 659).
- **Meta-rules `llm_synth` runs locally**, not cloud-side (`0b797b73`).
  Removes cloud-dependence for a core graduation primitive.
- **Streamlit dashboard deprecated** (`3ed9438c`). `gradata.ai` web dashboard
  now covers all panels (`/rules`, `/corrections`, `/self-healing`,
  `/observability`). Legacy CLI archived to
  `Gradata/.archive/dashboard_streamlit_deprecated_2026-04-23.py`.
- **`implicit_feedback` hook emit-only contract** (`aace2410`): main() returns
  None uniformly; signals emit via `IMPLICIT_FEEDBACK` event instead of as
  UserPromptSubmit injection to reduce prompt noise.

### Fixed

- **Bare `except: pass` blocks in core SDK** now log at DEBUG (`812eda9c`).
  Removes silent-failure class from Layer 0.
- **MISFIRE_PENALTY sign in `agent_graduation`** (`03ddb6f9`): penalties
  were being applied as bonuses.
- **Session-start hook**: correct lessons path + brain_prompt load +
  tighten stale-notes detection (`c2cc47b6`).
- **Cluster injection line count** now scopes to `<brain-rules>` block only,
  not full prompt (`118122a2`).
- **Public docs truth-pass** on cloud-vs-SDK boundary (`978e4c7f`): removed
  stale cloud-graduation claims from Pro tier marketing (`2c65bf2a`).

### Tests

- **3932 pass, 3 skip** (up from 2598 in v0.6.0). No xfail remaining.
- Meta-rules cloud-gated tests unskipped (`509bf927`).
- `pipeline_e2e`: removed "not yet implemented" skips, bumped fixtures (`2a781645`).
- `test_implicit_feedback`: coverage for text-speak + multi-signal inputs.

### Security / Governance

- **Supabase migrations now idempotent.** 014/015 wrapped in `DO $$` blocks
  that check `pg_constraint` for existing UNIQUE on same columns before
  adding. Prod state: both tables have pre-existing `_key` variants (from
  inline `UNIQUE()` in original CREATE TABLE) + the new `_unique` variants —
  redundant but harmless. Documented in `migrations/supabase/README.md`.
- `.gitignore` hardened against bash-redirect artifacts (`0`, `BrainDetail`),
  graphify cache files (`.graphify_*`), and run.log spray.

## [0.6.0] - 2026-04-15 — "We opened up"

**Strategic pivot:** the moat is not the algorithm code, it's the hosted service.
Gradata now open-sources everything and charges for the cloud tier.

### Breaking

- **License changed: AGPL-3.0-or-later → Apache-2.0.** SDK is now permissively open.
  Enterprise adoption unblocked. No copyleft linking obligations. No "commercial
  license" upsell. Past releases (v0.4, v0.5) remain under AGPL-3.0 forever —
  users who pinned those keep AGPL rights indefinitely.
- **`gradata-install` npm package deprecated.** Install path consolidated to
  `pip install gradata && gradata hooks install`. Old npm wrapper still functions
  with a deprecation notice; new IDE integrations go into the Python CLI.

### Added

- **Cloud algorithms now in SDK** — previously proprietary modules merged under
  `gradata.enhancements`:
  - `enhancements/graduation/` — `agent_graduation`, `judgment_decay`, `rules_distillation`
  - `enhancements/scoring/` — `brain_scores`, `calibration`, `correction_tracking`,
    `failure_detectors`, `gate_calibration`, `loop_intelligence`, `memory_extraction`,
    `reports`, `success_conditions`
  - `enhancements/bandits/` — `contextual_bandit`, `collaborative_filter`
  - `enhancements/profiling/` — `tone_profile` (universal style extraction)
- **Opt-in cloud sync client** (`gradata.cloud.sync`) — transmits aggregated
  metrics (NOT correction content) to the Gradata Cloud dashboard when user
  enables `cloud.sync = true`. Separate stricter opt-in for corpus contribution.
  Never blocks the learning loop on cloud availability.
- `get_maturity_phase()` helper on `self_improvement` (INFANT/ADOLESCENT/MATURE/STABLE
  based on session count).
- `format_metrics()` on `enhancements/metrics` — human-readable MetricsWindow summary.
- `examples/domain-profiles/` — `call_profile` and `sales_profile` as
  domain-adapter recipes (not SDK primitives).

### Changed

- Product positioning: "Corrections become behavioral rules that compound.
  Free SDK does the job. Paid cloud adds team brain, corpus network effects,
  and brain marketplace."
- All docs rewritten for Apache-2.0 + hosted SaaS pitch (docs/LICENSING.md,
  docs/cloud/overview.md, docs/faq.md, marketing strategy, launch strategy).
- `MetricsWindow.avg_edit_distance` renamed to `edit_distance_avg` internally
  (minor API cleanup for consistency).

### Coverage

- **2598 tests passing** (up from 2561). 37 previously cloud-gated tests
  now run. 19 legitimate skips remain (external API smoke tests, proprietary
  `meta_rules` flat module that lives only in the private cloud repo).
- 2 tests marked `@pytest.mark.xfail` for v0.7 reconciliation — API drift
  between the cloud_backup snapshot and current SDK constants.

### Security / Governance

- SDK is sole-authored by Oliver Le — unilateral relicense is legally clean
  (no CLA required, no external contributors to `_types.py` or `_scope.py`
  as of git history audit 2026-04-15).
- No secrets transmitted without explicit opt-in.

## [0.5.0] - 2026-04-15

First public release. Aligns `gradata-install` npm wrapper to 0.5.0.

### Added

- Self-healing engine: rule failure detection + auto-patching (PR #21)
- Cloud backend: Supabase schema, FastAPI sync endpoint, Railway deploy (PR #22)
- Wiki-aware rule injection with qmd semantic boost, Supabase wiki store (pgvector)
- `brain.on_notification()` API with 5 event formatters
- 19 Python hooks + installer + profile system (PR #20)
- Team, operator, seed, and health endpoints ([#28](https://github.com/Gradata/gradata/pull/28))
- Emails, legal pages, and auto-deploy CI ([#27](https://github.com/Gradata/gradata/pull/27))
- Rule-to-hook UX: list, remove, events, stale detection ([#30](https://github.com/Gradata/gradata/pull/30))
- `Brain.add_rule` API, runner profile gating, codex/cline/continue exports ([#31](https://github.com/Gradata/gradata/pull/31))
- Middleware adapters for OpenAI, Anthropic, LangChain, CrewAI ([#32](https://github.com/Gradata/gradata/pull/32))
- Rate limiting, Sentry wiring, and Stripe webhook hardening ([#33](https://github.com/Gradata/gradata/pull/33))
- Dashboard wired to real backend for team, operator, and clear-demo flows ([#34](https://github.com/Gradata/gradata/pull/34))
- GDPR data endpoints, DPA/SLA, security.txt, incident runbook ([#36](https://github.com/Gradata/gradata/pull/36))
- Plausible analytics on marketing site plus opt-in SDK telemetry ([#37](https://github.com/Gradata/gradata/pull/37))
- Full mkdocs Material docs site for gradata.ai/docs ([#38](https://github.com/Gradata/gradata/pull/38))
- Session-start hook injects meta-rules into LLM context ([#45](https://github.com/Gradata/gradata/pull/45))
- Honest A/B proof: `/public/proof` endpoint and ablation export ([#44](https://github.com/Gradata/gradata/pull/44))
- Outcome-first dashboard pivot driven by sim data ([#46](https://github.com/Gradata/gradata/pull/46))
- Visual graduation markers on the decay curve ([#47](https://github.com/Gradata/gradata/pull/47))
- `gradata-install` npm wrapper for one-command install ([#52](https://github.com/Gradata/gradata/pull/52))
- Claude Code plugin for `/plugin install gradata` ([#53](https://github.com/Gradata/gradata/pull/53))

### Changed

- Simplify pass across core SDK, enhancements layer, and cloud infra ([#40](https://github.com/Gradata/gradata/pull/40), [#41](https://github.com/Gradata/gradata/pull/41), [#42](https://github.com/Gradata/gradata/pull/42))
- Simplify pass on tracked-ops brain scripts ([#39](https://github.com/Gradata/gradata/pull/39))
- Rule-to-hook dispatcher: bundle N generated hooks into one for ~6x latency win ([#35](https://github.com/Gradata/gradata/pull/35))
- Pre-public repo cleanup and launch narrative docs ([#49](https://github.com/Gradata/gradata/pull/49), [#50](https://github.com/Gradata/gradata/pull/50))
- Populate `rule_patches` from `RULE_PATCHED` events in `/sync` ([#43](https://github.com/Gradata/gradata/pull/43))
- Remove orphaned `gradata-plugin/` subdir ([#54](https://github.com/Gradata/gradata/pull/54))

### Fixed

- Resolve 10 pyright type errors blocking CI ([#29](https://github.com/Gradata/gradata/pull/29))
- Add missing `export_ab_proof.py` script for proof pipeline ([#48](https://github.com/Gradata/gradata/pull/48))
- GitHub now recognizes AGPL-3.0 license ([#58](https://github.com/Gradata/gradata/pull/58))
- Move `LICENSE-NOTICE.md` to `docs/LICENSING.md` ([#59](https://github.com/Gradata/gradata/pull/59))
- 210 ruff errors across 106 files; bandit false-positive suppression; flaky graduation test on 3.12

### Infrastructure

- Ship full AGPL-3.0 license text ([#51](https://github.com/Gradata/gradata/pull/51))
- Add `ruff>=0.4` to dev dependencies; clean up stale `working-directory` in sdk-ci.yml

## [0.4.0] - 2026-04-06

### Added
- Behavioral instruction extraction — corrections now produce actionable instructions instead of diff fingerprints
- `brain.convergence()` — corrections-per-session trend metric (converging/converged/diverging)
- Instruction cache for LLM extraction results
- 21 template patterns for common correction types
- Meta-rule event emission (`meta_rule.created` bus event)

### Changed
- Repositioned from "procedural memory" to "AI that learns your judgment"
- Updated README with ablation experiment results (+13.2% quality improvement)
- Session counter no longer inflated by subagent/autoresearch runs

### Fixed
- Meta-rules were being created but `meta_rule.created` event was never emitted
- Auto-session-note hook incorrectly bumping session count for non-interactive runs

## [0.3.0] - 2026-04-05

### Added
- Event Bus — central nervous system wiring all components
- Two-tier embeddings (local + cloud)
- Rule effectiveness tracking via SessionHistory
- Context-aware rule ranking (scope, confidence, relevance, recency, fire count)
- Human-in-the-loop approval workflow
- Correction provenance tracking
- 200+ autoresearch code quality fixes

## [0.2.1] - 2026-04-04

### Fixed
- PyPI packaging and distribution fixes

## [0.2.0] - 2026-04-03

### Added
- Initial public release
- Graduation pipeline (INSTINCT → PATTERN → RULE)
- Meta-rule synthesis
- Compound score for brain quality
- CLI tools (init, correct, review, stats, manifest, doctor)
- OpenAI, Anthropic, LangChain, CrewAI integrations
- MCP server for IDE integration
- Encryption at rest support
