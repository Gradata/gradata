# Gradata

**Your AI gets better the more you use it. Prove it. Share it. Take it anywhere.**

Most AI tools forget everything between sessions. Memory tools store facts but never learn *how* you work. Gradata is different: it watches how you correct AI output, compounds those corrections into behavioral rules, and proves the improvement with real data.

```
Session 1:    You rewrite every email subject line
Session 20:   Brain notices the pattern, starts adjusting
Session 50:   Pattern proven — AI gets it right without your help
Session 100:  Correction rate dropped 40%. Brain proves it with data.
```

**Zero dependencies. One SQLite file. Works with any LLM.**

## Why

You use Claude Code every day. You correct the same mistakes over and over. Maybe you maintain a growing CLAUDE.md full of rules you wrote by hand.

Gradata captures your corrections automatically. Over sessions, it builds behavioral rules that apply to future output. Your AI stops making the same mistakes. And you can prove it.

Three things no LLM vendor will give you:

- **Portable.** Works across Claude, GPT, Cursor, and any MCP host. Switch tools, keep your brain.
- **Provable.** Quality manifest with real metrics: sessions trained, correction rate, active rules.
- **Shareable.** Package your expertise and let others rent it on the Gradata Marketplace.

## Installation

```bash
pip install gradata              # zero deps, works instantly
pip install gradata[embeddings]  # adds local embeddings
pip install gradata[gemini]      # adds Gemini embeddings (free tier)
pip install gradata[all]         # everything
```

Requires Python 3.11+. 752 tests passing.

## Quick Start

```python
from gradata import Brain

# Create a new brain
brain = Brain.init("./my-brain", domain="Engineering")

# Log AI output
brain.log_output("Here's the API design...", output_type="design_doc", self_score=7)

# Record correction (the learning signal)
brain.correct(
    draft="Here's the API design with REST endpoints...",
    final="Here's the API design with gRPC endpoints..."
)

# Get rules for next draft (grows over sessions)
rules = brain.apply_brain_rules("design_doc", {"audience": "backend_team"})

# Search brain knowledge
results = brain.search("API design patterns")

# Quality manifest (the proof)
manifest = brain.manifest()
print(f"Sessions: {manifest['metadata']['sessions_trained']}")
print(f"Active rules: {manifest['quality']['lessons_active']}")
```

## CLI

```bash
gradata init ./my-brain --domain Sales
gradata search "budget objections"
gradata embed                    # index knowledge files
gradata manifest --json          # quality proof
gradata stats
gradata validate --strict        # verify brain quality
gradata export                   # package for sharing
```

## MCP Integration

Works with any MCP-compatible host (Claude Code, Cursor, VS Code):

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

## Gradata Cloud

Connect to [Gradata Cloud](https://gradata.com) for server-side adaptation, cross-brain learning, and marketplace access:

```python
brain.connect_cloud()  # set GRADATA_API_KEY env var
```

## Documentation

Full docs at [gradata.github.io/gradata](https://gradata.github.io/gradata).

## Contributing

1. Fork the repo
2. Create a feature branch
3. Make changes and add tests
4. Submit a PR against `main`

## License

MIT
