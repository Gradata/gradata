# Gradata

Procedural memory for AI agents. Corrections become behavioral rules that compound over time.

Your AI keeps making the same mistakes. Gradata fixes that.

```bash
pip install gradata
```

Zero dependencies. Python 3.11+.

## Quick Start

```python
from gradata import Brain

brain = Brain.init("./my-brain")

# Your AI produces output. You fix it.
brain.correct(
    draft="We are pleased to inform you of our new product offering.",
    final="Hey, check out what we just shipped."
)

# Brain learns. Next time, inject rules into the prompt:
rules = brain.apply_brain_rules("write an email")
# → "[RULE:0.92] TONE: Use casual, direct language..."

# Prove the brain is getting better:
manifest = brain.manifest()
```

## How It Works

```
Human corrects AI output
       ↓
brain.correct(draft, final)
       ↓
Diff computed → severity classified → lesson created
       ↓
Confidence grows with each reinforcement:
  0.40 = INSTINCT (new, unproven)
  0.60 = PATTERN  (seen enough to trust)
  0.90 = RULE     (injected into every prompt)
       ↓
3+ related rules → META-RULE (general principle)
       ↓
brain.apply_brain_rules() → AI stops making that mistake
```

## Features

**Core learning loop:**
- `brain.correct(draft, final)` — capture corrections with automatic diff + severity classification
- `brain.apply_brain_rules(task)` — inject graduated rules into prompts
- `brain.manifest()` — mathematical proof the brain is improving (compound score)
- `brain.prove()` — paired t-test showing correction rate decreased after graduation

**Human-in-the-loop approval:**
- `brain.review_pending()` — list lessons awaiting approval
- `brain.approve_lesson(id)` / `brain.reject_lesson(id)` — pre-graduation veto gate
- `gradata review` CLI — approve/reject from terminal

**Encryption at rest:**
- `pip install gradata[encrypted]` — AES-128 via Fernet
- `Brain("./my-brain", encryption_key="...")` or `GRADATA_ENCRYPTION_KEY` env var
- Encrypt-on-close, decrypt-on-open. Zero plaintext at rest.

**Correction provenance:**
- Every lesson tracks which correction events created it
- Meta-rules link back to their source lessons
- Full audit trail: correction → lesson → rule → meta-rule

**23 optional agentic patterns** (`from gradata.contrib.patterns import ...`):
Pipeline, Guard, RAG, Reflection, Memory, MCP, Orchestrator, Q-Learning Router, and more. Pure Python, no dependencies.

**Integrations:** OpenAI, Anthropic, LangChain, CrewAI adapters included.

## CLI

```bash
gradata init ./my-brain              # Create a brain
gradata correct --draft "..." --final "..."  # Log a correction
gradata review                       # Approve/reject pending lessons
gradata stats                        # Brain health
gradata manifest --json              # Quality metrics
gradata search "topic"               # Search brain knowledge
gradata export                       # Package for sharing
gradata doctor                       # Diagnose issues
```

## MCP Server

Works with Claude Code, Cursor, Windsurf, and any MCP-compatible host:

```json
{
  "mcpServers": {
    "gradata": {
      "command": "python",
      "args": ["-m", "gradata.mcp_server"]
    }
  }
}
```

## Scaffolder

```bash
npx create-gradata ./my-brain
```

Auto-installs the SDK, runs the onboarding interview, brain ready in 30 seconds.

## What Makes This Different

| System | Remembers | Learns from corrections | Graduates rules | Proves improvement |
|--------|-----------|------------------------|-----------------|-------------------|
| Mem0 | Yes | No | No | No |
| Letta (MemGPT) | Yes | No | No | No |
| LangChain Memory | Yes | No | No | No |
| **Gradata** | Yes | **Yes** | **Yes** | **Yes** |

Everyone else builds *declarative memory* — "remember that I like short emails."

Gradata builds *procedural memory* — "after 12 corrections on email tone, graduated a RULE at 0.92 confidence: use casual, direct language." That's a learned behavior with a proof trail.

## Optional Extras

```bash
pip install gradata[encrypted]    # Encryption at rest (Fernet AES)
pip install gradata[embeddings]   # Local sentence-transformers
pip install gradata[all]          # Everything
```

## Architecture

```
src/gradata/
├── brain.py              # Brain class (public API)
├── _core.py              # Correction detection, diff engine
├── _events.py            # Append-only event log (JSONL + SQLite)
├── _types.py             # Lesson, LessonState, typed models
├── enhancements/
│   ├── self_improvement.py   # Graduation pipeline
│   ├── meta_rules.py         # Meta-rule emergence
│   └── diff_engine.py        # Edit distance, severity
├── rules/
│   ├── rule_engine.py        # Inject rules into prompts
│   └── scope.py              # Task classification
└── contrib/patterns/         # Optional agentic patterns
```

## Caveats

- v0.2.0 — API may change
- Local-only for now
- The graduation engine needs multiple sessions to produce rules. Don't expect results in one sitting.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

AGPL-3.0. Commercial license available for teams that need it.
