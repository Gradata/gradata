# Contributing to Gradata

Thanks for your interest in contributing. Here's how to get started.

## Setup

```bash
git clone https://github.com/gradata-systems/gradata.git
cd gradata/sdk
uv pip install -e ".[dev]" --system  # or: pip install -e ".[dev]"
```

## Development workflow

1. Create a branch from `main`
2. Make changes
3. Add tests for new functionality
4. Run the test suite: `pytest tests/ -q`
5. Run type checks: `pyright src/`
6. Run linting: `ruff check src/`
7. Submit a PR against `main`

## Code standards

- **Zero dependencies** for core package. If your change adds a required dependency, it will be rejected. Optional dependencies go in `[project.optional-dependencies]`.
- **Type hints** on all public API functions.
- **Tests required** for all new functionality. We use pytest. Target: every public method has at least one behavioral test.
- **No hardcoded paths or secrets.** All configuration via environment variables or brain config.

## Architecture

The SDK has 3 layers:

- **Layer 0 (`patterns/`)** -- base agentic patterns. Never imports from `enhancements/`.
- **Layer 1 (`enhancements/`)** -- brain-specific learning. May import from `patterns/`.
- **Shared types (`_types.py`)** -- data classes used by both layers.

Do not add cross-layer imports. If both layers need a type, put it in `_types.py`.

## Tests

```bash
pytest tests/ -q              # all tests
pytest tests/test_brain.py -v # specific file
pytest -k "test_correct"      # by name
```

## Licensing

Gradata is dual-licensed: AGPL-3.0 for open source, commercial license for enterprise. By contributing, you agree your contributions will be licensed under the same terms.

## Reporting issues

Open an issue on GitHub with:
- What you expected
- What happened
- Steps to reproduce
- Python version and OS
