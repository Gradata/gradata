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

## Attach an agent

After creating a brain, wire it into the agent you use every day:

```bash
gradata install --agent claude-code --brain ./my-brain
```

Supported targets are `claude-code`, `codex`, `gemini`, `cursor`, `hermes`,
`opencode`, and `all`.

Each `gradata install --agent ...` attempt appends a structured JSONL row to
`<gradata-config-dir>/install_measurements.jsonl` (usually
`~/.gradata/install_measurements.jsonl`, or `$XDG_CONFIG_HOME/gradata/` when set).
The row records `agent`, `status`, `action`, and `failure_kind` so launch metrics
can measure install success separately for Claude Code, Codex, Hermes, and Cursor:

- `failure_kind: none` — install succeeded or was already present.
- `failure_kind: code_failure` — the adapter ran but failed to write/parse config.
- `failure_kind: docs_friction` — `--agent all` could not detect a measured host
  config, so docs/onboarding must explain how to create or select that host.

## Verify

```bash
gradata --help
gradata --brain-dir ./my-brain doctor --no-cloud  # environment health check
gradata --brain-dir ./my-brain stats              # show brain stats
gradata --brain-dir ./my-brain audit              # data-flow audit
```

For a non-mutating offline smoke test that exercises init, agent-install dry
run, correction, recall, stats, and audit:

```bash
PYTHONPATH=src python examples/offline_quickstart_smoke.py
```

From Python:

```python
from gradata import Brain, __version__

print(__version__)                          # e.g. "0.5.0"
brain = Brain.init("./test-brain")
print(brain)                                # Brain('./test-brain')
```

Next: [Your First Brain](first-brain.md).
