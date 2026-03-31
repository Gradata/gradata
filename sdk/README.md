# Gradata

Your AI keeps making the same mistakes. Gradata fixes that.

## The problem

You correct your AI's output. It doesn't remember. You correct it again tomorrow. Other tools give AI memory. Gradata gives it the ability to change behavior.

## Install

```bash
pip install gradata
```

Zero dependencies. Python 3.11+.

## Setup (one time)

Add this to your Claude Code `settings.json`:

```json
{
  "mcpServers": {
    "gradata": {
      "command": "python",
      "args": ["-m", "gradata.mcp_server"]
    }
  },
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit",
        "command": "python -m gradata.hooks.auto_correct"
      }
    ]
  }
}
```

That's it. Gradata now watches your corrections and learns from them. The brain auto-creates at `~/.gradata/brain` on first run.

Also works with Cursor, VS Code, or any MCP-compatible host.

## What happens next

1. You correct your AI (change a word, rewrite a paragraph, fix code)
2. Gradata detects the correction, computes the diff, classifies the severity
3. The correction becomes a lesson. Lessons start as INSTINCT (low confidence)
4. If you keep reinforcing the same correction and never reverse it, confidence grows
5. At 0.60 confidence it becomes a PATTERN. At 0.90 it becomes a RULE
6. Rules inject into your next session automatically. The AI stops making that mistake.

## Python API

For building your own AI applications:

```python
from gradata import Brain

brain = Brain.init("./my-brain", domain="Engineering")

# Your AI writes something. You fix it.
brain.correct(
    draft="Here's the API design with REST endpoints...",
    final="Here's the API design with gRPC endpoints..."
)

# Next time, get rules before generating
rules = brain.apply_brain_rules("api_design")

# Search what the brain knows
results = brain.search("API design patterns")

# Proof of improvement
manifest = brain.manifest()
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

**23 agentic patterns** (pure Python, no dependencies):
pipeline, parallel execution, RAG (naive + smart), reflection/critique, guardrails (input + output), human-in-the-loop, scope classification, sub-agent orchestration, evaluator loops, memory (episodic + semantic + procedural), MCP bridge, rule engine + tracking, Q-learning router, context brackets, loop detection, task escalation, execute/qualify, reconciliation, middleware chain, agent modes.

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

**Optional extras:** `pip install gradata[embeddings]` for local sentence-transformers, `gradata[gemini]` for Gemini embeddings (free tier), `gradata[all]` for everything.

**Storage:** Everything lives in one SQLite file (`system.db`) plus markdown files. Portable. No external databases. No vendor lock-in.

## MCP tools

11 tools exposed via MCP:

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
| `brain_briefing` | Portable markdown briefing for any AI |

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

All data is event-sourced. Every correction, output log, and state change is an append-only event. Superseded events are marked with a `valid_until` timestamp but never deleted. The brain directory (markdown files + system.db) is the entire state. Copy it, back it up, move it between machines.

## What's coming

- **Quality dashboard** at [gradata.ai](https://gradata.ai): "fitness tracker for your AI"
- **Marketplace:** package and share trained brains
- **Team brains:** shared learning across organizations
- **Multi-brain orchestration:** compose expert brains via A2A protocol

## Caveats

- This is v0.1.0. The API will change.
- Local-only for now. Cloud sync is planned.
- The graduation engine needs multiple sessions to produce RULE-tier lessons. Don't expect results in one sitting.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT. See [LICENSE](LICENSE).
