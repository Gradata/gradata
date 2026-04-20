# Contributing to Gradata

Thanks for your interest in contributing.

## Development Setup

```bash
git clone https://github.com/Gradata/gradata.git
cd gradata
pip install -e ".[dev]"
pytest tests/
```

## Running Tests

```bash
pytest tests/ -x -q          # Full suite
pytest tests/test_core.py -v  # Specific module
```

## Code Style

- Python 3.11+, type hints required
- Run `pyright` for type checking (target: zero errors)
- Keep files under 500 lines
- No unnecessary abstractions — YAGNI

## Pull Requests

1. Fork the repo and create a branch from `main`
2. Write tests for new functionality (TDD preferred)
3. Ensure all tests pass and pyright is clean
4. Keep PRs focused — one feature or fix per PR

## Reporting Issues

Open an issue on [GitHub](https://github.com/Gradata/gradata/issues). Include:
- What you expected vs what happened
- Steps to reproduce
- Python version and OS

## License

By contributing, you agree that your contributions will be licensed under Apache-2.0.
