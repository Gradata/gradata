# Changelog

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
