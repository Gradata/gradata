# Gradata

Your AI keeps making the same mistakes. Gradata fixes that.

## The problem

You correct your AI's output. It doesn't remember. You correct it again tomorrow. You build a CLAUDE.md or system prompt full of rules you wrote by hand. That works until it doesn't.

Gradata watches your corrections, stores them as events in a local SQLite database, and makes that knowledge searchable. Over time, your AI stops repeating the same errors. One user, 71 sessions over 9 days, saw correction rates drop from 5.0 to 0.004 per output.

## Real results

All numbers from a single user (n=1) over 71 sessions. This is early data, not a peer-reviewed study.

| Metric | Value |
|---|---|
| Correction rate | 5.0 -> 0.004 per output (1,000x reduction) |
| Error categories extinct | 13 of 14 categories stopped recurring |
| Lessons graduated to rules | 48 of 107 (46%) |
| Adaptation Score | 96/100 |
| First Draft Acceptance | 100% for last 10 sessions |
| Correction severity | 0.40 -> 0.27 (trending down) |

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

**Integrations:** Anthropic, OpenAI, LangChain, CrewAI adapters included.

**Storage:** Everything lives in one SQLite file (`system.db`) plus markdown files. Portable. No external databases. No vendor lock-in.

## What's coming

The SDK captures corrections and stores knowledge locally. The full learning loop, where corrections graduate into lessons and lessons harden into permanent rules, runs via [gradata.ai](https://gradata.ai):

- **Graduation engine:** correction -> lesson -> rule pipeline with confidence scoring
- **Quality dashboard:** adaptation score, correction trends, category tracking
- **Marketplace:** package and share trained brains
- **Team brains:** shared learning across organizations

Full graduation engine + quality dashboard coming via gradata.ai.

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
brain.search() retrieves relevant knowledge
        |
        v
brain.manifest() proves improvement over time
```

All data is event-sourced. Every correction, output log, and state change is an immutable event in SQLite. The brain directory (markdown files + system.db) is the entire state. Copy it, back it up, move it between machines.

## Caveats

- This is v0.1.0. The API will change.
- The impressive numbers above come from one power user over 9 days. Your results will vary.
- The graduation engine (the part that turns corrections into permanent rules) is not in the open source SDK yet. It's coming via gradata.ai.
- Local-only for now. Cloud sync is planned.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

AGPL-3.0. See [LICENSE](LICENSE).
