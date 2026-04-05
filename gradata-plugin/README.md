# Gradata Claude Code Plugin

AI that learns your judgment. Auto-captures corrections and injects graduated rules.

## Install

```bash
claude plugin install gradata
```

The installer will:
1. Detect your Python installation
2. Offer to install the Gradata SDK via pip
3. Configure the brain directory at `~/.gradata/`

## How It Works

- **You correct Claude's output** (edit, rewrite, say "that's wrong")
- **Gradata extracts a behavioral instruction** from the correction
- **The instruction graduates** through INSTINCT -> PATTERN -> RULE as it proves reliable
- **Graduated rules inject automatically** into future sessions

## Commands

| Command | What it does |
|---|---|
| `/gradata status` | Brain health: rules, lessons, convergence |
| `/gradata review` | Review pending promotions |
| `/gradata prove` | Statistical proof of improvement |
| `/gradata forget` | Undo lessons |
| `/gradata doctor` | Health check and diagnostics |
| `/gradata promote` | Promote a rule to global scope |

## Architecture

The plugin runs a local Python daemon that wraps the Gradata SDK. Claude Code hooks talk to it via HTTP on localhost. No data leaves your machine.

```
Claude Code hooks -> HTTP -> localhost daemon -> Gradata SDK -> ~/.gradata/
```

## Requirements

- Python 3.10+
- Claude Code

## License

AGPL-3.0
