# AIOS Brain SDK

**AI that gets better the more you use it.**

AIOS Brain is a behavioral adaptation engine that sits on top of any LLM. It watches how users correct AI output, graduates those corrections into behavioral rules, and proves the improvement with real data.

## The Graduation Pipeline

```
INSTINCT (0.0-0.59) → PATTERN (0.60-0.89) → RULE (0.90+)
```

Every correction follows a lifecycle. Patterns that survive get promoted. Patterns that misfire get demoted. Patterns that never fire get killed. The brain compounds over sessions, not just stores data.

## Key Features

- **Zero dependencies** - pure Python + stdlib for base patterns
- **One file = one brain** - SQLite stores everything
- **Domain agnostic** - sales, engineering, recruiting, anything
- **Agent graduation** - agents learn and improve over sessions too
- **MCP compatible** - works with Claude Code, Cursor, and any MCP tool
- **605 tests** - comprehensive test coverage

## Quick Install

```bash
pip install aios-brain
```

## Next Steps

- [Quick Start](getting-started/quickstart.md) - get your first brain running in 5 minutes
- [Core Concepts](getting-started/concepts.md) - understand how graduation works
- [Architecture](architecture/overview.md) - 3-layer design explained
