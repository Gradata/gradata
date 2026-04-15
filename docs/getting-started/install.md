# Installation

## Requirements

- Python **3.11 or later**
- No external dependencies for core functionality (Python stdlib + SQLite is enough)

## Install

```bash
pip install gradata
```

This installs the core SDK. All base patterns, the event system, and the graduation pipeline work out of the box using only Python's standard library and SQLite.

### Optional extras

```bash
# Local embeddings (sentence-transformers, torch)
pip install "gradata[embeddings]"

# Google Gemini embeddings
pip install "gradata[gemini]"

# Encrypted brains (SQLCipher)
pip install "gradata[encrypted]"

# Everything, including dev tooling
pip install "gradata[all]"
```

### Development install

```bash
git clone https://github.com/Gradata/gradata.git
cd gradata
pip install -e ".[dev]"
```

The `dev` extra includes pytest, hypothesis, pyright, bandit, and coverage.

---

## `gradata init`

Bootstrap a new brain with the onboarding wizard:

```bash
gradata init ./my-brain
```

Flags:

| Flag | Description |
|------|-------------|
| `--domain` | Brain domain (`Sales`, `Engineering`, etc.) |
| `--name` | Brain name for the manifest |
| `--company` | Company name (creates `company.md`) |
| `--embedding` | Embedding provider: `local` or `gemini` |
| `--no-interactive` | Skip prompts (useful for CI) |

Non-interactive example:

```bash
gradata init ./sales-brain \
  --domain Sales \
  --name "Acme Outbound Brain" \
  --no-interactive
```

---

## Minimal config

A brain is a directory. `gradata init` creates it with the following layout:

```
my-brain/
├── system.db               # SQLite event log + facts + metrics
├── brain.manifest.json     # Machine-readable quality proof
├── .embed-manifest.json    # File hash tracking for delta embedding
├── lessons.md              # Graduated rules (human-readable)
└── taxonomy.json           # Custom tag taxonomy (optional)
```

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `GRADATA_BRAIN_DIR` | `./brain` | Path to brain directory |
| `GRADATA_LOG` | (none) | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `GRADATA_ENCRYPTION_KEY` | (none) | Enables at-rest encryption |

---

## Verify

```bash
gradata --help
gradata doctor            # environment health check
gradata stats             # show brain stats
```

From Python:

```python
from gradata import Brain, __version__

print(__version__)                          # e.g. "0.5.0"
brain = Brain.init("./test-brain")
print(brain)                                # Brain('./test-brain')
```

Next: [Your First Brain](first-brain.md).
