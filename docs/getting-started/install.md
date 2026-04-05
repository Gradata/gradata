# Installation

## Requirements

- Python 3.11 or later
- No external dependencies for core functionality

## Install

```bash
pip install gradata
```

This installs the core SDK with zero external dependencies. All base patterns, the event system, and the graduation pipeline work out of the box using only Python's standard library and SQLite.

## Optional Dependencies

For embedding and semantic search features, install extras:

```bash
# Local embeddings (sentence-transformers)
pip install gradata[embeddings]

# Google Gemini embeddings
pip install gradata[gemini]

# Everything
pip install gradata[all]
```

## Development Install

```bash
git clone https://github.com/gradata-systems/gradata.git
cd gradata
pip install -e ".[dev]"
```

The `dev` extra includes pytest, hypothesis, pyright, bandit, and coverage.

## Verify Installation

```bash
gradata --help
```

Or from Python:

```python
from gradata import Brain

brain = Brain.init("./test-brain")
print(brain)  # Brain('./test-brain')
```

## What Gets Created

When you initialize a brain, the SDK creates:

| File | Purpose |
|------|---------|
| `system.db` | SQLite database for events, facts, metrics, and embeddings |
| `brain.manifest.json` | Machine-readable quality proof (sessions trained, correction rate, graduation status) |
| `.embed-manifest.json` | File hash tracking for delta embedding |

Your knowledge files (markdown, text, etc.) live alongside these in the brain directory.
