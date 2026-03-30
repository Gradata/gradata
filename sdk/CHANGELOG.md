# Changelog

## v0.1.0 (2026-03-29) — Initial Release

First public release of the Gradata SDK.

### Core
- `Brain` class with full learning loop: `correct()` → lesson → `end_session()` graduation → `apply_brain_rules()` injection
- Severity-weighted confidence: trivial/minor/moderate/major/rewrite corrections move confidence differently
- Graduation tiers: INSTINCT (0.30) → PATTERN (0.60) → RULE (0.90)
- Meta-rules emerge from 3+ related graduated rules
- `brain.forget()` for deleting specific lessons (GDPR right-to-erasure)
- `brain.memory` property for episodic/semantic/procedural memory
- Context manager support: `with Brain("./brain") as b:`

### Patterns (15 reusable agentic patterns)
- Pipeline, Stage, SmartRAG, NaiveRAG, Guard, MCPBridge
- ParallelBatch, MemoryManager, HumanLoopGate, SubAgents
- Reflection, Scope, RuleTracker, Evaluator, Q-Learning Router

### Enhancements (11 modules)
- diff_engine, quality_gates, truth_protocol, meta_rules
- self_improvement, pattern_extractor, edit_classifier
- observation_hooks, learning_pipeline, rule_verifier, router_warmstart

### Infrastructure
- Zero required dependencies (all extras optional)
- SQLite-based persistence (no external services needed)
- FTS5 keyword search, sqlite-vec planned for vector similarity
- MCP server with 11 tools
- CLI with brain management commands
- 1127 tests, 11 skipped (cloud-only features)
