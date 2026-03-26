# CLI Reference

The `aios-brain` CLI provides command-line access to all brain operations.

## Commands

### `init`

Bootstrap a new brain directory.

```bash
aios-brain init ./my-brain
aios-brain init ./my-brain --domain Sales --name "My Brain"
aios-brain init ./my-brain --company "Acme Corp" --embedding gemini
aios-brain init ./my-brain --no-interactive
```

| Flag | Description |
|------|-------------|
| `--domain` | Brain domain (Sales, Engineering, etc.) |
| `--name` | Brain name for the manifest |
| `--company` | Company name (creates company.md) |
| `--embedding` | Embedding provider: `local` or `gemini` |
| `--no-interactive` | Skip terminal prompts |

### `search`

Search the brain.

```bash
aios-brain search "budget objections"
aios-brain search "Hassan Ali" --mode keyword
aios-brain search "email tone" --top 10
```

| Flag | Description |
|------|-------------|
| `--mode` | Search mode (default: auto) |
| `--top` | Number of results (default: 5) |

### `embed`

Embed brain files for semantic search.

```bash
aios-brain embed          # Delta (only changed files)
aios-brain embed --full   # Full re-embed
```

### `manifest`

Generate and display the brain manifest.

```bash
aios-brain manifest
aios-brain manifest --json    # Raw JSON output
```

### `stats`

Display brain statistics.

```bash
aios-brain stats
```

Output includes: markdown file count, database size, embedding chunk count, manifest status.

### `audit`

Run a data flow audit.

```bash
aios-brain audit
```

### `context`

Compile relevant context for a message.

```bash
aios-brain context "draft email to the CFO about pricing"
```

Returns formatted context from the brain's knowledge, suitable for prompt injection.

### `validate`

Verify brain quality and integrity.

```bash
aios-brain validate
aios-brain validate --strict    # Fail if trust grade < C
```

### `export`

Export the brain as a shareable archive.

```bash
aios-brain export
aios-brain export --mode no-prospects    # Exclude prospect data
aios-brain export --mode domain-only     # Patterns and rules only
```

### `install`

Install a brain from a marketplace archive.

```bash
aios-brain install brain-archive.zip
aios-brain install --list    # List installed brains
```

## Global Options

| Flag | Description |
|------|-------------|
| `--brain-dir` | Path to brain directory (default: current directory) |
| `--help` | Show help for any command |

## Examples

```bash
# Full workflow
aios-brain init ./sales-brain --domain Sales
aios-brain embed --full
aios-brain search "cold email best practices"
aios-brain manifest --json
aios-brain validate --strict
aios-brain export
```
