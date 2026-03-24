# Domain Pitfalls: SDK Production Readiness

**Domain:** Python SDK shipping to external users
**Researched:** 2026-03-24

## Critical Pitfalls

### Pitfall 1: Bare Exception Types Leak Implementation Details
**What goes wrong:** Users try to catch SDK errors but can't distinguish `ValueError` from brain.search() vs `ValueError` from their own code. They end up catching too broadly or not at all.
**Why it happens:** Natural to use built-in exceptions during prototyping.
**Consequences:** Users write `except Exception:` (swallows everything) or don't handle errors (crashes in production). Support burden increases.
**Prevention:** Custom exception hierarchy inheriting from a single `BrainError` base class. Every public method raises only `BrainError` subclasses.
**Detection:** grep for `raise ValueError|raise ImportError|raise RuntimeError` -- currently 40+ sites.

### Pitfall 2: py.typed Missing Breaks Type Checker Integration
**What goes wrong:** Type checkers (pyright, mypy) silently ignore all type information from the package. Users get `Any` for everything. Defeats the purpose of having type hints.
**Why it happens:** Easy to forget a marker file.
**Consequences:** IDE autocomplete doesn't work. Users think the SDK is untyped.
**Prevention:** Create `src/aios_brain/py.typed` (empty file). Add `Typing :: Typed` classifier.
**Detection:** `pyright --verifytypes aios_brain` after installing the package.

### Pitfall 3: DeprecationWarning Is Invisible by Default
**What goes wrong:** You add `warnings.warn("use X instead", DeprecationWarning)` but users never see it because Python filters DeprecationWarning by default in non-`__main__` code.
**Why it happens:** Python's warning filter system is counterintuitive. DeprecationWarning only shows in `__main__` and test runners.
**Consequences:** Users never learn about deprecated APIs until they break.
**Prevention:** Use `FutureWarning` for user-facing deprecations (always shown) OR use PEP 702 `@warnings.deprecated()` which works with static checkers. Document in version policy that `-Wd` flag shows all deprecations.
**Detection:** Run `python -Wd -c "import aios_brain"` to verify warnings appear.
**Source:** https://sethmlarson.dev/deprecations-via-warnings-dont-work-for-python-libraries

### Pitfall 4: Version String Drift
**What goes wrong:** `__version__` in `__init__.py` says "0.1.0" but `pyproject.toml` says "0.2.0" after someone bumps the project version but forgets the code.
**Why it happens:** Two sources of truth for the same value.
**Consequences:** `aios_brain.__version__` lies. Users report bugs with wrong version.
**Prevention:** Either (a) use `importlib.metadata.version("aios-brain")` at runtime, or (b) use hatch-vcs to generate `_version.py` from git tags.
**Detection:** CI check that compares `aios_brain.__version__` against `importlib.metadata.version("aios-brain")`.

## Moderate Pitfalls

### Pitfall 5: SQLite WAL Mode + Concurrent Processes
**What goes wrong:** Multiple processes open the same brain database. WAL mode handles concurrent readers but a second writer gets `SQLITE_BUSY` after the 5-second timeout.
**Prevention:** Already have `PRAGMA busy_timeout=5000`. For production: document single-writer constraint. Consider advisory lock file.

### Pitfall 6: MCP Server Path Traversal
**What goes wrong:** MCP client sends `brain_dir = "../../../../etc/passwd"` or similar.
**Prevention:** Validate that brain_dir resolves to an allowed parent directory. Use `Path.resolve()` and check it starts with expected prefix.

### Pitfall 7: ChromaDB Dependency Hell
**What goes wrong:** ChromaDB pulls in heavy native deps (onnxruntime, tokenizers). Users on ARM Linux or minimal Docker images can't install.
**Prevention:** Keep chromadb as optional dep (already done). Document the `sqlite-vec` migration path per S42 research. Provide fallback keyword search when vector store unavailable.

### Pitfall 8: No CHANGELOG Means Users Can't Assess Upgrade Risk
**What goes wrong:** User on v0.1.0 sees v0.3.0 exists but has no way to know what changed or if it's safe to upgrade.
**Prevention:** Adopt towncrier. Every PR that changes public API includes a changelog fragment.

## Minor Pitfalls

### Pitfall 9: Missing `__all__` in Subpackages
**What goes wrong:** `from aios_brain.patterns import *` imports implementation details.
**Prevention:** Already have `__all__` in main `__init__.py`. Verify subpackage `__init__.py` files also declare `__all__`.

### Pitfall 10: Docstring Format Inconsistency
**What goes wrong:** mkdocstrings can't parse mixed Google/NumPy/Sphinx docstring styles. API reference renders poorly.
**Prevention:** Standardize on Google-style docstrings (already majority pattern). Add ruff rule `D` (pydocstyle) to enforce.

### Pitfall 11: Test Files Ship in Wheel
**What goes wrong:** `tests/` directory gets included in the built wheel, bloating install size.
**Prevention:** Already handled -- `hatch.build.targets.wheel.packages = ["src/aios_brain"]` excludes tests. Verify with `pip install dist/*.whl && pip show -f aios-brain`.

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Exception hierarchy | Over-engineering: too many exception classes | Start with 8, add more only when users request them |
| Logging | Too verbose at default level | Default to WARNING. Debug is opt-in via env var. |
| Deprecation | Users never see warnings | Use FutureWarning, not DeprecationWarning |
| Documentation | Docs rot immediately | mkdocstrings auto-generates from code; no manual sync |
| MCP server | Security audit reveals more than path traversal | Budget 2x the estimated time for security work |

## Sources

- Seth Larson (Python security dev) on deprecation: https://sethmlarson.dev/deprecations-via-warnings-dont-work-for-python-libraries
- PEP 387 backward compat policy: https://peps.python.org/pep-0387/
- PEP 702 typing.deprecated: https://peps.python.org/pep-0702/
- SQLite WAL mode docs: https://www.sqlite.org/wal.html
- Stripe error hierarchy: https://github.com/stripe/stripe-python/blob/master/stripe/_error.py
- OpenAI exception design: https://github.com/openai/openai-python/blob/main/src/openai/_exceptions.py
