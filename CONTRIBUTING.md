# Contributing to Gradata

Thanks for contributing. This guide is short on purpose — read it end to end before your first PR.

## Quick Start

```bash
git clone https://github.com/Gradata/gradata.git
cd gradata
pip install -e ".[dev]"
pytest tests/ -x -q
```

TypeScript packages (dashboard, marketing, hooks) live under their own directories with `package.json`; `npm install && npm test` inside each.

## Branch Conventions

Branch off `main`. Prefix by intent:

- `feat/` — new capability
- `fix/` — bug fix
- `chore/` — tooling, infra, deps
- `docs/` — documentation only

One concern per PR. Rebase, don't merge, when updating from `main`.

## Licensing

Contributions are licensed under **AGPL-3.0-or-later**. By opening a PR you agree your changes may ship under that license. Dual-license details (including the commercial option) live in [docs/LICENSING.md](docs/LICENSING.md).

## DCO Sign-off (required)

Every commit must carry a `Signed-off-by:` trailer certifying the [Developer Certificate of Origin](https://developercertificate.org/). Use `-s`:

```bash
git commit -s -m "fix: handle empty brain dir"
```

The `dco` workflow blocks merges when any commit is missing the trailer. Fix with `git commit --amend -s` (single commit) or `git rebase --signoff main` (multiple).

## PR Checklist

Before requesting review:

- [ ] `pytest tests/ -x -q` passes
- [ ] `pyright` passes (Python); `tsc --noEmit` and `eslint .` pass (TypeScript)
- [ ] Docs updated for any public API changes (README, docstrings, `docs/`)
- [ ] All commits signed off (DCO)
- [ ] PR description explains **why**, not just what

## Code Style

- **Python**: 3.11+, type hints required. `ruff` for lint and format, `pyright` for types. Keep files under 500 lines.
- **TypeScript**: strict `tsc`, `eslint` clean. Prefer functions over classes.
- No unnecessary abstractions. YAGNI.

## Reporting Issues

Open an issue using one of the [issue templates](.github/ISSUE_TEMPLATE). Include your Python version, OS, and minimal repro.
