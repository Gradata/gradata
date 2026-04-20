# CLI Reference

The `gradata` command is the canonical CLI for working with a brain from the shell. Every command operates on a brain directory (by default, the current directory).

```bash
gradata --help
gradata <command> --help
```

## Global options

| Flag | Description |
|------|-------------|
| `--brain-dir <path>` | Path to brain directory (default: `./brain` or cwd) |
| `--help` | Show help for any command |

You can also export `GRADATA_BRAIN_DIR=./my-brain` to avoid repeating the flag.

---

## `init`

Bootstrap a new brain.

```bash
gradata init ./my-brain
gradata init ./my-brain --domain Sales --name "My Brain"
gradata init ./my-brain --company "Acme Corp" --embedding gemini
gradata init ./my-brain --no-interactive
```

| Flag | Description |
|------|-------------|
| `--domain` | Brain domain (`Sales`, `Engineering`, ...) |
| `--name` | Brain display name |
| `--company` | Company name; creates `company.md` |
| `--embedding` | Embedding provider: `local` or `gemini` |
| `--no-interactive` | Skip prompts (for CI) |

---

## `correct`

Record a correction from the CLI.

```bash
gradata correct \
  --draft "We are pleased to inform you..." \
  --final "Hey, check out what we shipped."

# Or from files
gradata correct --draft-file draft.txt --final-file final.txt
```

| Flag | Description |
|------|-------------|
| `--draft` | Original AI draft text |
| `--final` | User-edited final text |
| `--draft-file` | File containing draft |
| `--final-file` | File containing final |
| `--category` | Correction category override |
| `--session` | Session number override |

---

## `search`

Search the brain.

```bash
gradata search "formatting rules"
gradata search "common patterns" --mode keyword
gradata search "tone corrections" --top 10
```

| Flag | Description |
|------|-------------|
| `--mode` | `auto`, `keyword`, or `semantic` (default: `auto`) |
| `--top` | Number of results (default: 5) |

---

## `embed`

Embed brain files for semantic search.

```bash
gradata embed              # Delta: only changed files
gradata embed --full       # Full re-embed
```

Requires `pip install "gradata[embeddings]"`.

---

## `manifest`

Generate and display the brain manifest.

```bash
gradata manifest
gradata manifest --json
```

---

## `stats`

Display brain statistics: markdown file count, database size, embedding chunk count, manifest status.

```bash
gradata stats
```

---

## `audit`

Run a data flow audit.

```bash
gradata audit
```

---

## `context`

Compile relevant context for a message. Output is formatted for prompt injection.

```bash
gradata context "draft email to the CFO about pricing"
```

---

## `validate`

Verify brain quality and integrity.

```bash
gradata validate
gradata validate --strict    # Fail if trust grade < C
```

---

## `doctor`

Check environment and brain health. Diagnoses Python version, SQLite version, import paths, hook configuration.

```bash
gradata doctor
```

---

## `export`

Export the brain as a shareable archive.

```bash
gradata export
gradata export --mode no-prospects    # Exclude prospect data
gradata export --mode domain-only     # Patterns and rules only
```

---

## `install`

Install a brain from a marketplace archive.

```bash
gradata install brain-archive.zip
gradata install --list          # List installed brains
```

---

## `health`

Brain health report.

```bash
gradata health
```

---

## `report`

Generate reports.

```bash
gradata report --type rules
gradata report --type meta-rules
gradata report --type csv
gradata report --type metrics
```

---

## `watch`

Watch a directory for AI-generated file edits and log them as corrections automatically.

```bash
gradata watch ./workspace
```

---

## `diagnose`

Analyze correction patterns (free diagnostic, no embedding required).

```bash
gradata diagnose
```

---

## `convergence`

Show corrections-per-session convergence chart.

```bash
gradata convergence
```

---

## `review`

Review pending lessons for human approval.

```bash
gradata review                        # List pending lessons
gradata review --approve 7            # Approve lesson ID 7
gradata review --reject 8 --reason "too narrow"
gradata review --json
```

---

## `demo`

Copy a pre-trained demo brain to a directory.

```bash
gradata demo                  # Default ./demo-brain
gradata demo ./sales-demo
```

---

## `hooks`

Manage Claude Code hook integration.

```bash
gradata hooks install --profile standard
gradata hooks install --profile minimal
gradata hooks install --profile strict
gradata hooks status
gradata hooks uninstall
```

| Flag | Description |
|------|-------------|
| `--profile` | `minimal`, `standard`, `strict` (default: `standard`) |

See [Claude Code Setup](getting-started/claude-code.md) for what each profile installs.

---

## Full workflow example

```bash
gradata init ./sales-brain --domain Sales --no-interactive

# Capture corrections
gradata correct --draft "Hi there..." --final "Quick note..."
gradata correct --draft-file old.md --final-file new.md

# Embed and search
gradata embed --full
gradata search "cold email best practices"

# Prove and export
gradata manifest --json
gradata validate --strict
gradata export --mode domain-only

# Install hooks for enforcement
gradata hooks install --profile standard
gradata hooks status
```
