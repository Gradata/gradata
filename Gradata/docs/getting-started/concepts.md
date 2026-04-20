# Core Concepts

## How Brains Compound

Every time you correct the AI's output, the brain captures the edit. Over sessions, the brain identifies recurring patterns in your corrections and promotes them into rules that apply automatically.

Early on, a new correction is just a signal. If you keep making the same correction across multiple sessions, the brain gains confidence. If you stop making it (because the AI got it right), the rule is reinforced. If you contradict it, confidence drops.

Rules that prove themselves get applied to future output. Rules that don't get pruned. The brain cleans itself over time.

## Sessions

A session is a bounded unit of work. The brain tracks session numbers to measure:

- How often corrections happen (should decrease over time)
- Which corrections survive across sessions (signal vs. noise)
- Overall quality trends

## Scopes

Every correction is scoped to the context where it happened. A correction about email tone stays in the email scope. It won't affect code reviews or research tasks.

Scopes include:

- **Task type**: email, code review, research, demo prep
- **Audience**: executive, technical, peer
- **Domain**: sales, engineering, recruiting
- **Stakes**: high, medium, low

This prevents rules from leaking across contexts.

## The Manifest

`brain.manifest.json` is a machine-readable proof of brain quality:

```json
{
  "metadata": {
    "sessions_trained": 44,
    "domain": "Sales"
  },
  "quality": {
    "correction_rate": 0.23,
    "rules_active": 13,
    "rules_proven": 66
  }
}
```

The manifest regenerates from actual event data every session. It's the brain's resume: proof of how much training happened and what quality was achieved, without exposing raw data.

## Event-Sourced Storage

Everything is stored as events in a single SQLite database. No mutable state. Every correction, every output, every rule application is an append-only event.

```
my-brain/
├── system.db               # All structured data
├── brain.manifest.json     # Quality proof
├── knowledge/              # Your markdown knowledge files
└── taxonomy.json           # Custom tag definitions (optional)
```

Benefits:

- **Audit trail**: every state change has a timestamp and source
- **Portable**: one directory, one database, copy it anywhere
- **Rebuildable**: all derived state (metrics, manifest) can be recomputed from events

## Cross-Platform

The brain works with any MCP-compatible host:

- Claude Code
- Cursor
- VS Code Copilot Chat
- Any tool that supports the Model Context Protocol

Switch tools, keep your brain. Your corrections and rules travel with you.

## What's Next

- [Quick Start](quickstart.md) -- build your first brain
- [Training Guide](../guides/training.md) -- full training workflow
- [Gradata Cloud](../cloud/overview.md) -- server-side intelligence and marketplace
