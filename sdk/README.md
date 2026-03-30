# Gradata

Your AI keeps making the same mistakes. Gradata fixes that.

## The problem

You correct your AI's output. It doesn't remember. You correct it again tomorrow. You build a CLAUDE.md or system prompt full of rules you wrote by hand. That works until it doesn't.

Gradata watches your corrections, stores them as events in a local SQLite database, and makes that knowledge searchable. Over time, your AI stops repeating the same errors. One user, 71 sessions over 9 days, saw correction rates drop from 5.0 to 0.004 per output.

## Real results

All numbers below are from a single-user study (N=1) over 71 sessions across 9 days. Multi-user validation pending. Each claim cites its data source so you can verify independently.

| Metric | Value | Source |
|---|---|---|
| Correction rate | 5.0 per output (S31) to 0.004 per output (S70) | `events.jsonl` CORRECTION + OUTPUT event counts per session |
| Error categories eliminated | 13 of 14 correction categories stopped recurring (10+ session gap) | `events.jsonl` CORRECTION events grouped by `data.category` |
| Corrections analyzed | 59 total: 35 moderate, 24 major, 0 rewrite severity | `events.jsonl` edit-distance severity classification |
| Lessons graduated to rules | 48 of 107 (45%) reached RULE confidence threshold | `lessons.md` + `lessons-archive.md` status counts |

The graduation engine that produced these numbers runs server-side. The open source SDK handles correction logging, event storage, brain search, and the manifest that proves improvement happened.

## Install

```bash
pip install gradata
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add gradata
```

Zero required dependencies. Python 3.11+.

Optional extras:

```bash
pip install gradata[embeddings]  # local sentence-transformers
pip install gradata[gemini]      # Gemini embeddings (free tier)
pip install gradata[all]         # everything
```

## Quick start

```python
from gradata import Brain

# Create a new brain
brain = Brain.init("./my-brain", domain="Engineering")

# Log what the AI produced
brain.log_output("Here's the API design...", output_type="design_doc", self_score=7)

# When you correct the AI's output, record it
brain.correct(
    draft="Here's the API design with REST endpoints...",
    final="Here's the API design with gRPC endpoints..."
)

# Search brain knowledge
results = brain.search("API design patterns")

# Get rules for the next draft (grows over sessions)
rules = brain.apply_brain_rules("design_doc", {"audience": "backend_team"})

# Quality manifest (the proof your brain is improving)
manifest = brain.manifest()
```

## MCP server

Works with Claude Code, Cursor, VS Code, or any MCP-compatible host:

```json
{
  "mcpServers": {
    "gradata": {
      "command": "python",
      "args": ["-m", "gradata.mcp_server", "--brain-dir", "./my-brain"]
    }
  }
}
```

## CLI

```bash
gradata init ./my-brain --domain Sales
gradata search "budget objections"
gradata stats
gradata manifest --json
gradata validate --strict
gradata export
gradata doctor
```

## What's included

**Core brain operations:** correction logging, event storage (event-sourced, append-only), FTS5 full-text search, brain manifest generation, brain export/import.

**15 agentic patterns** (pure Python, no dependencies):
pipeline, parallel execution, dependency graphs, RAG (naive + smart), reflection/critique, guardrails (input + output), human-in-the-loop, scope classification, sub-agent orchestration, evaluator loops, memory (episodic + semantic + procedural), MCP bridge, rule tracking.

**Learning pipeline** (end-to-end, runs on every correction):

```
brain.correct(draft, final)
        |
        v
observe (100% tool-use capture)
        |
        v
cluster (group related corrections via cosine similarity + temporal gating)
        |
        v
discriminate (filter noise: is this correction worth learning from?)
        |
        v
classify (5 memory types: narrative, fact, prediction, profile, cross-brain)
        |
        v
route (Q-Learning RL router picks best agent for similar future tasks)
        |
        v
context bracket (FRESH/MODERATE/DEEP/CRITICAL degradation management)
```

**Graduation engine** (INSTINCT -> PATTERN -> RULE):
- Severity-weighted confidence scoring (trivial to rewrite)
- FSRS-inspired diminishing returns (harder to reach RULE threshold)
- Session-type-aware decay (sales lessons skip system sessions)
- Ablation-verified causal testing
- Meta-rule emergence from 3+ graduated rules

**Quality controls:**
- CARL behavioral contracts with MUST/SHOULD/MAY enforcement tiers
- Execute/Qualify verification loop (fresh re-reads, 3-attempt recovery)
- Plan reconciliation (UNIFY: PASS/GAP/DRIFT scoring against acceptance criteria)
- 4-status task escalation (DONE/DONE_WITH_CONCERNS/NEEDS_CONTEXT/BLOCKED)
- Context brackets prevent late-session quality degradation

**Integrations:** Anthropic, OpenAI, LangChain, CrewAI adapters included.

**Install profiles:** `lite` (core patterns only), `standard` (recommended), `full` (everything), `research` (RL router + observation hooks + meta-rules).

**Storage:** Everything lives in one SQLite file (`system.db`) plus markdown files. Portable. No external databases. No vendor lock-in.

## MCP tools

10 tools exposed via MCP:

| Tool | What it does |
|---|---|
| `brain_search` | Search brain knowledge |
| `brain_correct` | Log a correction (triggers full learning pipeline) |
| `brain_log_output` | Track AI outputs for quality measurement |
| `brain_manifest` | Generate quality proof manifest |
| `brain_health` | Health report with compound score |
| `brain_pipeline_stats` | Learning pipeline stats (stages, router, clusters) |
| `brain_context_bracket` | Current context degradation level |
| `brain_route_suggest` | RL-based agent routing suggestion |
| `brain_capabilities` | SDK module availability with source attribution |
| `brain_benchmark` | Run standard learning quality benchmark |

## How it works

```
You correct AI output
        |
        v
brain.correct(draft, final)
        |
        v
Diff computed, edits classified, CORRECTION event stored
        |
        v
Learning pipeline: observe → cluster → discriminate → route → bracket
        |
        v
Graduation: INSTINCT (0.30) → PATTERN (0.60) → RULE (0.90)
        |
        v
brain.apply_brain_rules() injects graduated rules into next session
        |
        v
brain.manifest() proves improvement over time (compound score 0-100)
```

All data is event-sourced. Every correction, output log, and state change is an immutable event in SQLite. The brain directory (markdown files + system.db) is the entire state. Copy it, back it up, move it between machines.

## What's coming

- **Quality dashboard** at [gradata.ai](https://gradata.ai): "fitness tracker for your AI"
- **Marketplace:** package and share trained brains
- **Team brains:** shared learning across organizations
- **Multi-brain orchestration:** compose expert brains via A2A protocol

## Caveats

- This is v0.1.0. The API will change.
- The numbers above come from one power user over 9 days. Your results will vary.
- Local-only for now. Cloud sync is planned.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

AGPL-3.0. See [LICENSE](LICENSE).
