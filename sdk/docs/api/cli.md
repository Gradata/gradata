# CLI Reference

The `gradata` CLI provides command-line access to all brain operations.

## Commands

### `init`

Bootstrap a new brain directory.

```bash
gradata init ./my-brain
gradata init ./my-brain --domain Sales --name "My Brain"
gradata init ./my-brain --company "Acme Corp" --embedding gemini
gradata init ./my-brain --no-interactive
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
gradata search "budget objections"
gradata search "Hassan Ali" --mode keyword
gradata search "email tone" --top 10
```

| Flag | Description |
|------|-------------|
| `--mode` | Search mode (default: auto) |
| `--top` | Number of results (default: 5) |

### `embed`

Embed brain files for semantic search.

```bash
gradata embed          # Delta (only changed files)
gradata embed --full   # Full re-embed
```

### `manifest`

Generate and display the brain manifest.

```bash
gradata manifest
gradata manifest --json    # Raw JSON output
```

### `stats`

Display brain statistics.

```bash
gradata stats
```

Output includes: markdown file count, database size, embedding chunk count, manifest status.

### `audit`

Run a data flow audit.

```bash
gradata audit
```

### `context`

Compile relevant context for a message.

```bash
gradata context "draft email to the CFO about pricing"
```

Returns formatted context from the brain's knowledge, suitable for prompt injection.

### `validate`

Verify brain quality and integrity.

```bash
gradata validate
gradata validate --strict    # Fail if trust grade < C
```

### `export`

Export the brain as a shareable archive.

```bash
gradata export
gradata export --mode no-prospects    # Exclude prospect data
gradata export --mode domain-only     # Patterns and rules only
```

### `install`

Install a brain from a marketplace archive.

```bash
gradata install brain-archive.zip
gradata install --list    # List installed brains
```

## Global Options

| Flag | Description |
|------|-------------|
| `--brain-dir` | Path to brain directory (default: current directory) |
| `--help` | Show help for any command |

## Examples

```bash
# Full workflow
gradata init ./sales-brain --domain Sales
gradata embed --full
gradata search "cold email best practices"
gradata manifest --json
gradata validate --strict
gradata export
```
