# Changelog

## v0.3.0 (2026-04-05) -- Nervous System

The graduation pipeline is now a connected nervous system. Every component publishes to and subscribes from a central event bus. No more parallel islands.

### Event Bus
- Central `EventBus` on every Brain instance (`brain.bus`)
- 11 event types: `correction.created`, `lesson.graduated`, `lesson.demoted`, `lesson.killed`, `meta_rule.created`, `rules.injected`, `session.started`, `session.ended`, `correction.implicit`, `tool.finding`, `tool.finding.acted`
- Sync and async handlers with 5-second timeout and error isolation
- Subscribe to any event: `brain.bus.on("correction.created", handler)`

### Semantic Embeddings
- Two-tier embedding client: lightweight local model (free) or cloud API (paid)
- Lessons embedded on creation (async, non-blocking)
- `cluster_lessons_by_similarity()` for semantic meta-rule synthesis
- Meta-rules now form by meaning, not just keyword overlap

### Session History (Rule Effectiveness)
- Tracks which rules were injected per session
- Tracks which rules were corrected (not working) vs survived (working)
- Effectiveness scores feed back into graduation: effective rules get confidence boosts
- Persists cross-session via claude-mem integration

### Context-Aware Rule Ranking
- New `rank_rules()` with weighted formula: 30% scope + 25% confidence + 20% context relevance + 15% recency + 10% fire count
- QMD integration: rules boosted by relevance to current working context
- Effectiveness bonus/penalty from session history
- Optional `context_keywords` parameter for framework users

### Hooks (Claude Code / MCP)
- `tool-finding-capture.js` -- lint/test findings become brain corrections when acted on
- `session-history-sync.js` -- persists rule effectiveness to claude-mem at session end
- `inject-brain-rules.js` -- QMD context query for smarter rule ranking at session start
- All hooks ship with SDK, scaffolded by `gradata init`

### Autoresearch Hardening
- 30 edge case fixes in graduation engine (_core.py, meta_rules.py, _manifest_quality.py)
- Guards: NaN propagation, confidence clamping [0,1], None inputs, division by zero, empty collections
- Fixed data loss bug: propagated confidence not persisted after meta-rule discovery
- Fixed severity gating off-by-one
- 2,534 lines of dead code removed (3 dead modules, 37 dead functions)

### Tests
- 1339 tests (up from 1300), 0 failures, 7 skipped

## v0.2.0 (2026-04-04) -- Clean Launch

SDK restructured for public release. Single commit baseline.

### Core
- Brain class with full learning loop
- Severity-weighted confidence graduation (INSTINCT > PATTERN > RULE)
- Meta-rules from 3+ related graduated rules
- MCP server with 11 tools
- CLI with 16 commands
- 1300 tests passing

## v0.1.0 (2026-03-29) -- Initial Release

First public release of the Gradata SDK.

### Core
- `Brain` class with full learning loop: `correct()` > lesson > `end_session()` graduation > `apply_brain_rules()` injection
- Severity-weighted confidence: trivial/minor/moderate/major/rewrite
- Graduation tiers: INSTINCT (0.30) > PATTERN (0.60) > RULE (0.90)
- Meta-rules emerge from 3+ related graduated rules
- `brain.forget()` for GDPR right-to-erasure
- Context manager support

### Patterns (15 reusable agentic patterns)
- Pipeline, Stage, SmartRAG, NaiveRAG, Guard, MCPBridge
- ParallelBatch, MemoryManager, HumanLoopGate, SubAgents
- Reflection, Scope, RuleTracker, Evaluator, Q-Learning Router

### Enhancements (11 modules)
- diff_engine, quality_gates, truth_protocol, meta_rules
- self_improvement, pattern_extractor, edit_classifier
- observation_hooks, learning_pipeline, rule_verifier, router_warmstart

### Infrastructure
- Zero required dependencies
- SQLite-based persistence
- FTS5 keyword search
- MCP server with 11 tools
- CLI with brain management commands
- 1127 tests
