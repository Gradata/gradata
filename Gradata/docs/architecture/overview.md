# Architecture Overview

## Three-Layer Design

```
┌─────────────────────────────────────────────┐
│  Layer 2: Trained Brain (Data)              │
│  events.jsonl · system.db · prospects/      │
│  sessions/ · brain.manifest.json            │
├─────────────────────────────────────────────┤
│  Layer 1: Enhancements (19 modules)         │
│  self_improvement · correction_tracking     │
│  quality_gates · brain_scores · carl        │
│  diff_engine · edit_classifier · metrics    │
├─────────────────────────────────────────────┤
│  Layer 0: Patterns (15 modules)             │
│  orchestrator · pipeline · parallel         │
│  reflection · evaluator · memory · rag      │
│  guardrails · human_loop · sub_agents       │
│  rule_engine · rule_tracker · scope · tools │
│  mcp                                        │
└─────────────────────────────────────────────┘
```

## Import Rules

The layers enforce strict dependency direction:

- **Layer 0** (`patterns/`): Never imports from `enhancements/`. Pure logic, zero external dependencies.
- **Layer 1** (`enhancements/`): Imports from `patterns/` but never the reverse.
- **Layer 2** (brain data): Accessed through Layer 0 and Layer 1 APIs.

This keeps Layer 0 patterns reusable across any brain, and prevents enhancement-specific logic from leaking into base patterns.

## Event-Sourced Data Model

All brain state derives from events. There are no mutable domain tables.

```
Event → system.db (append-only) → Derived Views (metrics, manifests, reports)
```

An event looks like:

```json
{
  "ts": "2026-03-25T10:15:00Z",
  "session": 42,
  "type": "CORRECTION",
  "source": "brain.correct",
  "data_json": {"severity": "major", "edit_distance": 0.72, "category": "TONE"},
  "tags_json": ["category:TONE", "severity:major"]
}
```

Benefits of event sourcing:

- **Auditability**: Every state change has a timestamp and source.
- **Replayability**: Rebuild any derived view by replaying events.
- **No data loss**: Corrections are never overwritten.
- **Time travel**: Query brain state at any point in history.

## The Core Loop

```
User Prompt
    → AI generates draft
    → brain.log_output(draft)
    → User edits draft
    → brain.correct(draft, final)
        → Diff Engine (edit distance + severity)
        → Edit Classifier (tone/content/structure/factual/style)
        → Pattern Extractor (behavioral patterns from edits)
        → Graduation (INSTINCT → PATTERN → RULE)
    → brain.apply_brain_rules(task, context)
        → Scope Matcher (task type + audience + domain)
        → Rule Engine (select matching rules)
        → Prompt Injection (rules formatted for LLM)
    → AI generates better draft
```

## Behavioral Contracts vs Learned Principles

Gradata keeps direct user contracts separate from learned principles:

- `DirectiveRegistry` stores static, direct user contracts. These are explicit
  constraints supplied by a user, domain profile, or application integration,
  and they should be treated as user-owned requirements.
- `MetaRule` stores learned emergent principles. These are inferred from
  corrections, supporting lessons, and observed behavior, and they carry
  confidence and provenance because they are learned rather than declared.

Both can influence prompt injection, but they should not be merged into one data
model. The boundary is source of authority: direct contract vs emergent lesson.

## Storage

Everything lives in one directory:

```
my-brain/
├── system.db               # SQLite: events, facts, metrics, embeddings
├── brain.manifest.json     # Machine-readable quality proof
├── .embed-manifest.json    # File hash tracking for delta embedding
├── knowledge/              # Your markdown knowledge files
├── prospects/              # Prospect notes (if sales domain)
├── sessions/               # Session summaries
└── taxonomy.json           # Custom tag taxonomy (optional)
```

`system.db` is the single source of truth. Markdown files are knowledge inputs. The manifest is a derived output.

## MCP Integration

The SDK exposes brain tools via the Model Context Protocol (MCP), so any MCP-compatible host can use the brain:

```bash
python -m gradata.mcp_server --brain-dir ./my-brain
```

See [MCP Integration Guide](../guides/mcp.md) for details.
