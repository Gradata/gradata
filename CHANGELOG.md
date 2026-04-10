# Changelog

## [0.5.0] - 2026-04-10

### Added
- Self-healing engine: rule failure detection + auto-patching (PR #21)
- Cloud backend: Supabase schema, FastAPI sync endpoint, Railway deploy config (PR #22)
- Wiki-aware rule injection: semantic boost from qmd wiki pages
- Notification system: `brain.on_notification()` API with 5 event formatters
- Supabase wiki store: pgvector semantic search for cloud rule injection
- 19 Python hooks + installer + profile system (PR #20)

### Fixed
- 210 ruff errors across 106 files
- Bandit false positives suppressed with explanations
- Flaky graduation test stabilized for Python 3.12
- CodeRabbit review findings across PRs #20, #21, #22

### Changed
- CI: added ruff>=0.4 to dev dependencies
- CI: fixed sdk-ci.yml paths (removed stale working-directory)

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
