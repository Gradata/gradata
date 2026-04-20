# Contributing

Thanks for your interest in contributing to Gradata. This page covers the dev setup, test commands, and PR style. If you prefer the short version, see [`CONTRIBUTING.md`](https://github.com/Gradata/gradata/blob/main/CONTRIBUTING.md) in the repo.

## Development setup

```bash
git clone https://github.com/Gradata/gradata.git
cd gradata/Gradata
pip install -e ".[dev]"
pytest tests/
```

The SDK lives under the `Gradata/` subfolder of the repo; all SDK commands run from there. The `dev` extra installs pytest, hypothesis, pyright, bandit, ruff, and coverage.

On Windows, use PowerShell or WSL. The hooks invoke Python directly (`python -m gradata.hooks.*`), so Python must be on your `PATH`.

## Running tests

```bash
# Full suite — aim for ~1 min
pytest tests/

# Single module
pytest tests/test_brain.py -v

# Single test
pytest tests/test_brain.py::test_correct_emits_event -v

# Coverage
pytest --cov=gradata --cov-report=term-missing
```

Hypothesis-based tests live under `tests/property/` and are slow. If you need to run a subset:

```bash
pytest tests/property/ -x --hypothesis-show-statistics
```

## Linting and type-checking

```bash
ruff check .
ruff format --check .
pyright
bandit -r src/
```

Target: zero ruff errors, zero pyright errors, zero bandit HIGH findings.

## Code style

- Python 3.11 or later.
- Type hints everywhere (`from __future__ import annotations` is fine).
- Keep files under 500 lines. If you're near the limit, split.
- Module-level `__all__` lists public surface. Everything else is private.
- Public functions have docstrings. Internal helpers don't need them.
- No unnecessary abstractions. YAGNI.

## Commit style

Short imperative subject line, optional body:

```text
fix(brain): guard against empty draft in correct()

correct() used to KeyError when draft was empty. Return a no-op event
instead, keeping the learning loop valid.
```

Prefixes we use:

- `feat:` — new capability
- `fix:` — bugfix
- `docs:` — docs only
- `refactor:` — structural change, no behavior diff
- `test:` — test additions
- `chore:` — tooling, CI, deps

## Pull requests

1. Fork the repo and create a branch from `main`.
2. Write tests before or alongside the change.
3. Run `pytest`, `pyright`, `ruff check`. All three must be green.
4. Keep PRs focused — one feature or fix per PR.
5. Update `CHANGELOG.md` under `## [Unreleased]` if the change is user-facing.
6. For docs changes, run `mkdocs build --strict` and ensure no warnings.

## Docs

Docs live in `docs/` and are built with [MkDocs Material](https://squidfunk.github.io/mkdocs-material/).

```bash
pip install mkdocs mkdocs-material
mkdocs serve     # http://localhost:8000
mkdocs build --strict
```

Strict build must pass before merging any docs PR.

## Reporting issues

Open an issue on [GitHub](https://github.com/Gradata/gradata/issues). Include:

- What you expected vs what happened.
- Steps to reproduce (smallest script that triggers the bug).
- Python version and OS.
- The full traceback if any.

For security issues, email `security@gradata.ai` instead of opening an issue.

## License

By contributing, you agree your contributions will be licensed under **Apache-2.0**, the same license as the rest of the SDK.

See [`LICENSE`](https://github.com/Gradata/gradata/blob/main/LICENSE) for the full text.
