# Technology Stack

**Project:** aios-brain SDK production readiness
**Researched:** 2026-03-24

## Current Stack (Keep)

The existing stack is correct. Do not change it.

| Technology | Version | Purpose | Why Keep |
|------------|---------|---------|----------|
| Hatchling | latest | Build backend | Simple, fast, PEP 621 native. Used by pip itself. |
| Python 3.11+ | 3.11-3.12 | Runtime | `datetime.UTC`, `tomllib`, `ExceptionGroup` -- all used |
| SQLite (stdlib) | bundled | Event store | Zero deps, WAL mode, portable, proven |
| Ruff | latest | Lint + format | Replaces flake8+isort+black in one tool |
| Pyright | latest | Type checking | Strict mode path to py.typed compliance |
| Bandit | latest | Security lint | Already configured, catches common issues |
| Pytest | 8.0+ | Testing | Industry standard |
| Hypothesis | 6.0+ | Property testing | Already in dev deps, not yet used in tests |

## Add for Production

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| mkdocs-material | latest | Documentation site | PydanticAI, FastAPI, Typer all use it. Best Python SDK docs theme. |
| mkdocstrings[python] | latest | API reference from docstrings | Auto-generates reference docs from type hints + docstrings |
| mike | latest | Doc versioning | Serves multiple doc versions (v0.1, v1.0) from same site |
| towncrier | latest | Changelog generation | Fragment-based changelogs, used by pip, twisted, attrs |

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Build backend | Hatchling | Poetry | Poetry forces lock files, adds complexity for library packages |
| Docs | mkdocs-material | Sphinx | Markdown > RST for contributor friendliness. Material theme is modern. |
| Changelog | towncrier | manual CHANGELOG.md | Fragment-per-PR scales; manual doesn't |
| Type checker | Pyright | mypy | Pyright is faster, better VS Code integration, already configured |
| Vector store | sqlite-vec | ChromaDB | Zero native deps, bundles with SQLite (per S42 research). Migration TBD. |

## Dev Dependencies to Add

```bash
# Documentation
pip install mkdocs-material mkdocstrings[python] mike

# Changelog
pip install towncrier

# Already present but unused
# hypothesis -- activate in tests
```

## pyproject.toml Additions Needed

```toml
[project.optional-dependencies]
docs = [
    "mkdocs-material>=9.0",
    "mkdocstrings[python]>=0.24",
    "mike>=2.0",
]

# Add to project table:
# license = {file = "LICENSE"}  # PEP 639 style (replaces license string)
```

## Sources

- Stripe SDK: https://github.com/stripe/stripe-python (Hatchling build, py.typed)
- OpenAI SDK: https://github.com/openai/openai-python (Hatchling build, custom exceptions)
- PydanticAI: mkdocs-material for docs
- PEP 561: https://peps.python.org/pep-0561/ (py.typed marker spec)
- PEP 639: License file handling in pyproject.toml
