# AGENTS.md

> Guidance for AGENTS.md-aware coding agents (Hermes Agent, Codex, Gemini CLI, OpenCode, etc.) working in this repository.
>
> Claude Code reads `CLAUDE.md` instead — keep both files in sync when changing project-wide guidance.

## Project

**Gradata** — Procedural memory for AI agents. Corrections become behavioral rules that compound over time.

- Language: Python 3.11+
- Distribution: PyPI as `gradata`
- License: Apache-2.0
- Architecture: Local-first SQLite + JSONL event log, optional cloud sync
- Public entry point: `from gradata import Brain`

## Scope

This folder contains **only** the public `gradata` SDK that ships to https://github.com/Gradata/gradata.

Out-of-scope sibling directories (do **not** import from or write into these from `gradata/*`):

| Directory | Contains |
|-----------|----------|
| `../Sprites/` | Private sales agents, prospect data, Brain runtime data |
| `../Hausgem/` | Private HausGem ecommerce work |

If you find yourself touching files in `../Sprites/` or `../Hausgem/` from inside Gradata code, stop — that is a layering bug.

## Commands

All commands run from the `Gradata/` directory.

```bash
# Install dev environment
uv sync --extra all --extra dev

# Run tests (full suite)
pytest tests/

# Run a single test file or case
pytest tests/test_brain.py -xvs
pytest tests/test_brain.py::TestBrain::test_correct -xvs

# Skip integration tests (the CI default)
pytest -m "not integration"

# Run integration tests explicitly (hits external LLM APIs)
pytest -m integration

# Lint + format
ruff check src/ tests/
ruff format src/ tests/

# Type check
pyright src/

# Security scan
bandit -r src/

# Build wheel
uv build

# CLI doctor health check
python -m gradata.cli doctor

# HTTP daemon (port 8765, JS/TS clients)
python -m gradata.daemon

# MCP server (stdio, IDE integration)
python -m gradata.mcp_server
```

## Architecture

### Strict layering rule

Lower layers **never** import from higher layers. Violations are bugs and should be flagged in code review.

```
Layer 2 — Public API        brain.py, cli.py, daemon.py, mcp_server.py
Layer 1 — Enhancements      enhancements/*, rules/
Layer 0 — Primitives        _types.py, _db.py, _events.py, _paths.py, _file_lock.py …
Layer 0 — Patterns          contrib/patterns/*
```

### Zero required dependencies

`pyproject.toml` lists `dependencies = []`. The base package is pure Python + stdlib. Optional extras gate all heavy deps:

- `embeddings` — `sentence-transformers` (local embeddings)
- `gemini` — `google-genai` (Gemini embeddings, free tier)
- `encrypted` — `cryptography` (AES-GCM encrypted `system.db`)
- `ranking` — `bm25s` (BM25 rule ranking; pure Python, no numpy)
- `adapters-mem0` — `mem0ai` (external memory adapter)

Code that uses optional deps must guard imports with `try / except ImportError` at the **call site**, never at module level. This keeps `import gradata` cheap on minimal installs.

### Brain data model

The central entity is a `Lesson` (in `src/gradata/_types.py`), which travels through a lifecycle managed by `LessonState`:

```
INSTINCT → PATTERN → RULE → META_RULE
   ↓          ↓        ↓
KILLED    INSTINCT  ARCHIVE   (contradiction / decay / graduation)
```

A Brain is a directory containing:

- `system.db` — SQLite event log, facts, metrics, embeddings (WAL mode)
- `events.jsonl` — append-only event log (portable, crash-safe)
- `lessons.md` — graduated behavioral rules (human-readable)
- `brain.manifest.json` — machine-readable quality proof
- `rule_graph.json` — rule relationship graph
- `.embed-manifest.json` — file hash tracking for delta embedding

### Public API

The canonical correction loop:

```python
from gradata import Brain

brain = Brain.init("./my-brain")          # or Brain("./my-brain") to open existing

# Capture a correction → extract behavioral rule
brain.correct(draft="original draft", final="user-edited version")

# Apply learned rules to a new task
rules = brain.apply_brain_rules("write an email to the team")

# Search the event/lesson log
results = brain.search("budget objections")

# Quality + export
manifest = brain.manifest()
brain.export("./exports/my-brain.zip")
```

`brain.correct()` is THE entry point for the headline product promise. Other correction paths (implicit feedback, agent-graduation, log_output) are secondary and may be aliases or private.

## Rules for agents working in this repo

### Always do

- **Read before edit.** Open the target file in full before modifying it.
- **Tests first when fixing bugs.** Add a failing test that reproduces the bug, then fix it. The test must remain green after the fix.
- **Run the smallest relevant test after each change.** `pytest tests/test_brain.py -xvs` is faster than the full suite.
- **Honor the layering rule.** If your change crosses Layer 0 → 2, flag it in the PR description.
- **Single source of truth.** If you find duplicate-purpose modules (`events_bus.py` vs `_events.py`, `inspection.py` vs `brain_inspection.py`, `_config.py` vs `_config_paths.py`) — pick one and document the migration; do not add a third.

### Never do

- **Never use bare `except: pass`.** Use typed exceptions, or at minimum `logger.warning(...)` with `exc_info=True`. Silent-swallow in a memory product is the worst-possible failure mode.
- **Never write `rule_graph.json` non-atomically.** Use the atomic-write helper. One crash mid-write = poisoned brain.
- **Never assume thread-safety on `Brain`.** It is documented as NOT thread-safe. Concurrent writes from `daemon.py` (HTTP) and `mcp_server.py` (stdio) require process-level coordination.
- **Never commit scratch files.** `.tmp/`, `.archive/`, `sessions/handoff-*.md`, files literally named `0` or `BrainDetail` — these belong in `.gitignore`, not on `main`.
- **Never leak private-sibling paths into public docs/code.** No references to `../Sprites/`, `../Hausgem/`, Oliver's email, OneDrive paths, or Sprites-specific examples from inside `gradata/*`.
- **Never push to `origin/main` directly.** All changes go through PR review.

## Testing conventions

- **Unit tests** live in `tests/test_*.py` and run on every CI push (no LLM calls, deterministic).
- **Integration tests** are marked `@pytest.mark.integration` and skipped by default (they hit real LLM APIs and cost money).
- **Test isolation:** `tests/conftest.py` sets `BRAIN_DIR` via `tmp_path` per test. If you call `Brain.init()` directly inside a test, set the env var first so `_paths.py` module cache refreshes.
- **The 4 deterministic guarantees** of the product MUST have tests:
  1. Correction in → rule extracted out
  2. Rule retrieved/applied in subsequent session
  3. Contradicting evidence lowers confidence
  4. Stale rules decay below threshold

## Commit / PR conventions

```
<type>(<scope>): <imperative description>

[optional body — what + why, not how]

[optional trailers]
```

Types: `feat`, `fix`, `docs`, `refactor`, `perf`, `test`, `chore`, `revert`

PR description must include:

- **Summary:** what the PR does in 1-3 sentences
- **Test plan:** which tests were added/changed and confirmed passing
- **Layering check:** confirms no Layer 0 → 2 import was introduced
- **Risk:** any backwards-compat concerns, schema migrations, or runtime contract changes

## Optional: AI agent coordination

When working on multi-file changes (3+ files, cross-module refactor, schema changes), agents can coordinate via the council skill (`/council` slash command in Hermes Agent). For single-file edits and 1-2 line bug fixes, just do the work.
