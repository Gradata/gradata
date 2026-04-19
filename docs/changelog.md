# Changelog

The canonical changelog lives in [`CHANGELOG.md`](https://github.com/Gradata/gradata/blob/main/CHANGELOG.md) in the repo. A mirror is below for convenience.

## [0.6.1] — 2026-04-19

### Added

- `gradata seed` + `gradata mine` CLI commands for seeding rules and extracting corrections from session logs (#sdk)
- BM25 context relevance scoring for JIT rule ranking; Beta lower-bound default raised to 0.85 (#101)
- Meta-Harness A–D: per-rule injection anchors, pipeline rewriter, agent-rewritten graduation scoring, synthesized prompt injection (#hooks)
- Multi-tenant SDK: `tenant_id`, visibility, cluster, and `sync_state` columns; env-first brain resolution (#102)
- SDK-native hook daemon (opt-in) (#99)
- `rule_verifier` wired into rule pipeline behind `GRADATA_RULE_VERIFIER` flag
- RetainOrchestrator + dedup-safe `emit()` writes (#98)
- 100% test coverage for calibration, failure detectors, gate calibration, memory extraction, reports, and success conditions

### Changed

- `gradata.patterns` is **deprecated** — emits `DeprecationWarning` on first import. Migrate to `gradata.contrib.patterns` or `gradata.rules`. Will be removed in **v0.8.0**. (#110)
- `Alert` canonical definition consolidated to `gradata.enhancements.quality_monitoring`; duplicate removed from `gradata.patterns`. (#109)
- `integrations/` collapsed into `middleware/` with deprecation shims
- `self_improvement.py` split into `_confidence` + `_graduation` submodules
- `rule_engine.py` split into 5-file package
- GRADATA_* env var access centralized in `_env.py`

### Fixed

- Scope domain leakage in `agent_precontext` (#hooks)
- 4 confidence-math bugs in graduation pipeline
- Windows-safe atomic append via `msvcrt.locking`
- 67 + 66 ruff violations across SDK (#103, #100)
- `__version__` now reads from installed package metadata

### Security

- HTTPS enforced at all `CloudClient` network boundaries
- Cloud→local rule injection vector removed
- Lesson text sanitized at all trust-boundary crossings
- SDK pen-test findings 4, 5, 11, 12 resolved

## [0.5.0] — 2026-04-10

### Added

- Self-healing engine: rule failure detection and auto-patching (PR #21)
- Cloud back-end: Supabase schema, FastAPI sync endpoint, Railway deploy config (PR #22)
- Wiki-aware rule injection: semantic boost from qmd wiki pages
- Notification system: `brain.on_notification()` with 5 event formatters
- Supabase wiki store: pgvector semantic search for cloud rule injection
- 19 Python hooks + installer + profile system (PR #20)

### Fixed

- 210 ruff errors across 106 files
- Bandit false positives suppressed with explanations
- Flaky graduation test stabilized for Python 3.12
- CodeRabbit review findings across PRs #20, #21, #22

### Changed

- CI: added `ruff>=0.4` to dev dependencies
- CI: fixed `sdk-ci.yml` paths (removed stale `working-directory`)

## [0.4.0] — 2026-04-06

### Added

- Behavioral instruction extraction — corrections now produce actionable instructions instead of diff fingerprints
- `brain.convergence()` — corrections-per-session trend metric (`converging`, `converged`, `diverging`)
- Instruction cache for LLM extraction results
- 21 template patterns for common correction types
- Meta-rule event emission (`meta_rule.created` bus event)

### Changed

- Repositioned from "procedural memory" to "AI that learns your judgment"
- Updated README with ablation experiment results (+13.2% quality improvement)
- Session counter no longer inflated by subagent/autoresearch runs

### Fixed

- Meta-rules were being created but `meta_rule.created` event was never emitted
- Auto-session-note hook was incorrectly bumping session count for non-interactive runs

## [0.3.0] — 2026-04-05

### Added

- Event Bus — central nervous system wiring all components
- Two-tier embeddings (local + cloud)
- Rule effectiveness tracking via `SessionHistory`
- Context-aware rule ranking (scope, confidence, relevance, recency, fire count)
- Human-in-the-loop approval workflow
- Correction provenance tracking
- 200+ autoresearch code quality fixes

## [0.2.1] — 2026-04-04

### Fixed

- PyPI packaging and distribution fixes.

## [0.2.0] — 2026-04-03

### Added

- Initial public release
- Graduation pipeline (INSTINCT → PATTERN → RULE)
- Meta-rule synthesis
- Compound score for brain quality
- CLI tools (`init`, `correct`, `review`, `stats`, `manifest`, `doctor`)
- OpenAI, Anthropic, LangChain, CrewAI integrations
- MCP server for IDE integration
- At-rest encryption support
