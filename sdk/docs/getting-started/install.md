# Installation

## Requirements

- Python 3.11 or later
- No external dependencies for core functionality

## Install

```bash
pip install aios-brain
```

This installs the core SDK with zero external dependencies. All base patterns, the event system, and the graduation pipeline work out of the box using only Python's standard library and SQLite.

## Optional Dependencies

For embedding and semantic search features, install extras:

```bash
# Local embeddings (sentence-transformers)
pip install aios-brain[embeddings]

# Google Gemini embeddings
pip install aios-brain[gemini]

# Everything
pip install aios-brain[all]
```

## Development Install

```bash
git clone https://github.com/sprites-ai/aios-brain.git
cd aios-brain
pip install -e ".[dev]"
```

The `dev` extra includes pytest, hypothesis, pyright, bandit, and coverage.

## Verify Installation

```bash
aios-brain --help
```

Or from Python:

```python
from aios_brain import Brain

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
