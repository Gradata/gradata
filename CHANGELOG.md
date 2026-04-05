# Changelog

## v0.2.1 (2026-04-05)

### Added
- `brain.session` property — auto-tracked session counter from event log
- `SESSION_END` event emitted by `end_session()` — native session counting in the SDK
- PyPI publication — `pip install gradata` works from the internet
- More project URLs in package metadata (Repository, Bug Tracker, Changelog)
- Python 3.13 classifier

### Changed
- Author: Oliver Le (oliver@gradata.com)
- Project URLs point to github.com/Gradata/gradata

## v0.2.0 (2026-04-04) — Initial Release

First public release of the Gradata SDK. Published to GitHub.

### Core
- `Brain` class with full learning loop: `correct()` → lesson → `end_session()` graduation → `apply_brain_rules()` injection
- Severity-weighted confidence: trivial/minor/moderate/major/rewrite corrections move confidence differently
- Graduation tiers: INSTINCT (0.40) → PATTERN (0.60) → RULE (0.90)
- Meta-rules emerge from 3+ related graduated rules
- `brain.forget()` for deleting specific lessons (GDPR right-to-erasure)
- `brain.observe()` for extracting facts from conversations
- `brain.detect_implicit_feedback()` for behavioral signal detection
- Context manager support: `with Brain("./brain") as b:`
- Human-in-the-loop approval gate: `review_pending()`, `approve_lesson()`, `reject_lesson()`
- Encryption at rest via Fernet AES (`pip install gradata[encrypted]`)
- Correction provenance: every lesson tracks its source correction events

### Patterns (21 reusable agentic patterns)
- Pipeline, Stage, SmartRAG, NaiveRAG, Guard, MCPBridge
- ParallelBatch, MemoryManager, HumanLoopGate, SubAgents
- Reflection, Scope, RuleTracker, Evaluator, Q-Learning Router
- TaskEscalation, Orchestrator, LoopDetection, AgentModes, Middleware, Reconciliation

### Enhancements
- diff_engine, quality_gates, truth_protocol, meta_rules
- self_improvement, learning_pipeline, rule_verifier, router_warmstart

### Infrastructure
- Zero required dependencies (all extras optional)
- SQLite-based persistence (no external services needed)
- FTS5 keyword search with hybrid retrieval
- MCP server with 11 tools
- CLI with brain management commands
- `npx create-gradata` scaffolder
- 1,301 tests passing
