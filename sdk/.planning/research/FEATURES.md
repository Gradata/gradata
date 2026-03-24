# Feature Landscape: Production SDK Gaps

**Domain:** Python SDK production readiness (7 dimensions)
**Researched:** 2026-03-24

## Dimension 1: SDK Packaging

### What Production SDKs Do

**Stripe SDK** (github.com/stripe/stripe-python):
- `py.typed` marker file in package root
- `__version__` in `__init__.py` (single source of truth via `_version.py`)
- `entry_points` for CLI tools
- `LICENSE` file (MIT)
- `CHANGELOG.md` with every release
- Classifiers including `Typing :: Typed`

**OpenAI SDK** (github.com/openai/openai-python):
- `py.typed` marker
- `__version__` imported from `._version`
- `VERSION` constant for programmatic access
- `DEFAULT_TIMEOUT`, `DEFAULT_MAX_RETRIES` as package-level constants
- Re-exports all exception classes from `__init__.py`

### What We Have
- `__version__ = "0.1.0"` -- good, but hardcoded (not synced with pyproject.toml)
- `entry_points` for `aios-brain` CLI -- good
- `__all__` with comprehensive exports -- good
- NO `py.typed` marker
- NO `LICENSE` file in sdk/ directory
- NO `CHANGELOG.md`
- NO `Typing :: Typed` classifier
- Version string duplicated (pyproject.toml AND `__init__.py`)

### Gap Assessment

| Gap | Priority | Effort | Notes |
|-----|----------|--------|-------|
| `py.typed` marker file | CRITICAL | 5 min | Create empty file at `src/aios_brain/py.typed` |
| `Typing :: Typed` classifier | CRITICAL | 1 min | Add to pyproject.toml classifiers |
| LICENSE file | CRITICAL | 5 min | PyPI rejects packages without it in some configs |
| CHANGELOG.md | NICE-TO-HAVE | 2 hrs | Use towncrier for fragment-based generation |
| Version sync | NICE-TO-HAVE | 30 min | Use hatch-vcs or importlib.metadata to single-source |
| examples/ directory | NICE-TO-HAVE | 4 hrs | 3-5 runnable examples (init brain, search, correct, export) |

---

## Dimension 2: Error Handling

### What Production SDKs Do

**Stripe** (`stripe/_error.py`):
```
StripeError(Exception)
  +-- APIError
  +-- APIConnectionError
  +-- AuthenticationError
  +-- CardError
  +-- IdempotencyError
  +-- InvalidRequestError
  +-- PermissionError
  +-- RateLimitError
  +-- SignatureVerificationError
```
Every error carries: `message`, `http_status`, `code`, `json_body`, `headers`.

**OpenAI** (`openai/_exceptions.py`):
```
OpenAIError(Exception)
  +-- APIError(message, request, body, code, param, type)
      +-- APIConnectionError
      +-- APITimeoutError
      +-- APIStatusError(status_code, response)
          +-- BadRequestError (400)
          +-- AuthenticationError (401)
          +-- RateLimitError (429)
          +-- InternalServerError (500)
```

**google-cloud-python** (`google.api_core.exceptions`):
- Maps HTTP status codes to exception classes
- All carry `grpc_status_code` and `errors` list
- `RetryError` wraps failed retry attempts

### What We Have
- Bare `ValueError`, `ImportError`, `RuntimeError`, `FileNotFoundError`, `KeyError`, `TypeError`, `NotImplementedError`
- 40+ raise sites across the codebase
- No custom exception classes
- No error codes
- No retry logic

### Gap Assessment

| Gap | Priority | Effort | Notes |
|-----|----------|--------|-------|
| Custom exception hierarchy | CRITICAL | 4 hrs | `BrainError` base, 6-8 subclasses |
| Error codes (string enum) | CRITICAL | 2 hrs | `"BRAIN_NOT_FOUND"`, `"EMBED_FAILED"`, etc. |
| Wrap existing raises | CRITICAL | 3 hrs | Replace 40+ bare raises with typed exceptions |
| Retry logic for embed/search | NICE-TO-HAVE | 3 hrs | Exponential backoff for ChromaDB/network calls |

**Proposed hierarchy:**
```python
class BrainError(Exception):
    """Base for all aios-brain exceptions."""
    code: str  # machine-readable error code

class BrainNotFoundError(BrainError): ...       # brain dir missing
class BrainCorruptedError(BrainError): ...      # db/files corrupted
class ConfigurationError(BrainError): ...       # bad config values
class DependencyError(BrainError): ...          # optional dep missing (replaces ImportError)
class ValidationError(BrainError): ...          # input validation failed
class EmbeddingError(BrainError): ...           # embed/search failures
class ExportError(BrainError): ...              # export/install failures
class MigrationError(BrainError): ...           # schema migration failures
```

---

## Dimension 3: Observability

### What Production SDKs Do

**OpenAI SDK:**
- `_setup_logging()` called at import time
- `OPENAI_LOG=debug` environment variable
- Structured log messages with request IDs
- OpenTelemetry instrumentation available via separate package (`opentelemetry-instrumentation-openai-v2`)
- Emits spans for chat completions, embeddings

**Stripe SDK:**
- `stripe.log = "debug"` module-level toggle
- Logs request/response pairs with request IDs
- `stripe.set_app_info()` for user-agent tracking

**google-cloud-python:**
- `logging.getLogger("google.cloud")` namespace
- DEBUG level shows full request/response
- Built-in OpenTelemetry span creation

### What We Have
- `logging.getLogger(__name__)` in 2 of ~30 modules (watcher.py, evaluator.py)
- No debug mode toggle
- No environment variable for log level
- Event system exists (`_events.py`) but no observability hooks for SDK consumers
- No request/operation IDs for tracing

### Gap Assessment

| Gap | Priority | Effort | Notes |
|-----|----------|--------|-------|
| Consistent `logging.getLogger(__name__)` | CRITICAL | 2 hrs | Add to all modules, standard Python convention |
| `AIOS_BRAIN_LOG` env var | CRITICAL | 30 min | `debug`/`info`/`warning` levels |
| Operation IDs | NICE-TO-HAVE | 3 hrs | UUID per brain operation for log correlation |
| User-facing event hooks | NICE-TO-HAVE | 4 hrs | `brain.on("correction", callback)` pattern |
| OpenTelemetry spans | NOT NEEDED YET | 8 hrs | Premature -- no production deployments yet |

---

## Dimension 4: Backward Compatibility

### What Production SDKs Do

**Stripe:**
- API version pinning (`stripe.api_version = "2024-12-18"`)
- Deprecation notices in CHANGELOG with migration instructions
- Old API versions supported for 24 months

**OpenAI:**
- `warnings.deprecated` (PEP 702) on old methods
- `DEFAULT_MAX_RETRIES` etc. as named constants (changeable without breaking)

**Python ecosystem standard** (PEP 387):
- DeprecationWarning for 2 minor versions before removal
- `@warnings.deprecated()` decorator (Python 3.13+, backport via `typing_extensions`)

### What We Have
- Schema migrations in `_migrations.py` -- good for data backward compat
- No deprecation warnings anywhere
- No version policy documented
- No API stability guarantees

### Gap Assessment

| Gap | Priority | Effort | Notes |
|-----|----------|--------|-------|
| Deprecation decorator utility | CRITICAL | 1 hr | `def deprecated(message, removal_version)` |
| Version policy doc | CRITICAL | 1 hr | "What we promise about breaking changes" |
| Apply deprecation to any renamed APIs | NICE-TO-HAVE | 2 hrs | As-needed basis |
| API stability tiers | NICE-TO-HAVE | 1 hr | Mark experimental vs stable in docstrings |

---

## Dimension 5: Documentation

### What Production SDKs Do

**PydanticAI** (best-in-class Python AI SDK docs):
- mkdocs-material with custom theme
- Auto-generated API reference via mkdocstrings
- Examples directory with runnable scripts
- "Getting Started" guide separate from API reference
- Versioned docs via mike

**Stripe:**
- Hosted at docs.stripe.com
- Every method has: description, parameters table, example request, example response
- Language-specific code samples

### What We Have
- README.md with usage examples -- decent but not a docs site
- Docstrings on most public methods -- good foundation
- No generated API reference
- No examples/ directory
- No hosted docs site

### Gap Assessment

| Gap | Priority | Effort | Notes |
|-----|----------|--------|-------|
| mkdocs.yml + basic site | NICE-TO-HAVE | 3 hrs | Uses existing docstrings |
| API reference generation | NICE-TO-HAVE | 2 hrs | mkdocstrings reads type hints |
| examples/ directory (3-5 scripts) | NICE-TO-HAVE | 4 hrs | init, search, correct, export, MCP |
| Quickstart guide | NICE-TO-HAVE | 2 hrs | Separate from README |
| Hosted on GitHub Pages | NICE-TO-HAVE | 1 hr | `mike deploy` in CI |

---

## Dimension 6: Security

### What Production SDKs Do

**Stripe:**
- Webhook signature verification (`SignatureVerificationError`)
- API key never logged (redacted in debug output)
- Strict TLS enforcement
- No eval/exec anywhere

**OpenAI:**
- API key from env var by default (`OPENAI_API_KEY`)
- Connection pooling with safe defaults
- Input size limits

**General Python SDK security:**
- Bandit linting (we already have this)
- No `pickle.loads` on untrusted data
- No `eval`/`exec` on user input
- SQL parameterized queries (not string formatting)

### What We Have
- Bandit configured and in dev deps -- good
- SQLite uses parameterized queries in `_events.py` -- good
- No credential handling (SDK doesn't manage API keys) -- N/A for now
- No `eval`/`exec` in codebase -- good
- MCP server exposes brain operations -- needs audit for path traversal

### Gap Assessment

| Gap | Priority | Effort | Notes |
|-----|----------|--------|-------|
| MCP server path traversal audit | CRITICAL | 2 hrs | Ensure brain_dir is sandboxed |
| Input validation on Brain() path | NICE-TO-HAVE | 1 hr | Reject `../` traversal, symlink following |
| SQL injection review | NICE-TO-HAVE | 1 hr | Audit all sqlite3.execute calls |
| SBOM | NOT NEEDED YET | -- | Zero required deps means minimal supply chain risk |

---

## Dimension 7: Testing Maturity

### What Production SDKs Do

**Stripe SDK:** Unit tests + integration tests against mock API server. No property-based testing.

**OpenAI SDK:** Unit tests + recorded HTTP cassettes for integration tests. Prism mock server.

**Hypothesis in Python ecosystem:**
- Property-based tests find ~50x more mutations per test than unit tests (empirical research, OOPSLA 2025)
- Used by 5% of Python developers (6th most popular testing framework)
- Most effective for: data serialization roundtrips, parser correctness, collection operations

### What We Have
- 537 tests across 9 test files -- strong count
- `hypothesis>=6.0` in dev deps but 0 property-based tests
- No integration tests (e.g., full brain lifecycle)
- No mutation testing
- No fuzz testing
- Coverage tool in dev deps but unclear if measured

### Gap Assessment

| Gap | Priority | Effort | Notes |
|-----|----------|--------|-------|
| Property-based tests for event serialization | NICE-TO-HAVE | 4 hrs | Roundtrip: emit -> query -> verify |
| Property-based tests for Brain.search | NICE-TO-HAVE | 3 hrs | Arbitrary queries never crash |
| Coverage measurement + gate | NICE-TO-HAVE | 1 hr | `pytest --cov=aios_brain --cov-fail-under=80` |
| Integration test: full brain lifecycle | NICE-TO-HAVE | 4 hrs | init -> log -> correct -> search -> export |
| Mutation testing | NOT NEEDED YET | -- | 537 tests is well above the bar for v1.0 |
| Fuzz testing | NOT NEEDED YET | -- | No untrusted network input in core SDK |

---

## Anti-Features

Features to explicitly NOT build right now.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| OpenTelemetry integration | No production deployments; adds dep | Use stdlib logging, add OTel later |
| SBOM generation | Zero required deps = no supply chain risk | Revisit when deps > 0 |
| Mutation testing | 537 tests already strong | Property-based tests have better ROI |
| Plugin/extension system | Premature abstraction | Hard-code patterns, extract plugin API at v2.0 |
| Async API | Brain operations are local I/O, not network | SQLite is sync anyway; async wrapper adds no value |

## Feature Dependencies

```
py.typed -> API reference docs (mkdocstrings reads type info)
Exception hierarchy -> Logging (log exceptions with codes)
Exception hierarchy -> Deprecation system (DeprecationWarning is an exception subclass)
Logging -> Debug mode (env var sets log level)
All above -> Documentation (docs describe the stable surface)
```

## MVP for "Shippable to Strangers"

**Must have (16 hours):**
1. Custom exception hierarchy + error codes (6 hrs)
2. `py.typed` + LICENSE + Typing::Typed classifier (10 min)
3. Structured logging in all modules + `AIOS_BRAIN_LOG` env var (3 hrs)
4. Deprecation utility function (1 hr)
5. Version policy document (1 hr)
6. MCP server path traversal audit (2 hrs)
7. examples/ directory with 3 scripts (3 hrs)

**Should have (12 hours):**
1. mkdocs-material site with API reference (5 hrs)
2. CHANGELOG.md + towncrier setup (2 hrs)
3. Property-based tests for event roundtrip (4 hrs)
4. Coverage gate in CI (1 hr)

## Sources

- Stripe Python SDK: https://github.com/stripe/stripe-python
- Stripe error handling: https://docs.stripe.com/error-handling?lang=python
- OpenAI Python SDK: https://github.com/openai/openai-python
- OpenTelemetry for GenAI: https://opentelemetry.io/blog/2024/otel-generative-ai/
- PEP 561 (py.typed): https://peps.python.org/pep-0561/
- PEP 702 (deprecated decorator): https://peps.python.org/pep-0702/
- PEP 387 (backward compat policy): https://peps.python.org/pep-0387/
- Seth Larson on deprecation warnings: https://sethmlarson.dev/deprecations-via-warnings-dont-work-for-python-libraries
- OOPSLA 2025 PBT study: https://cseweb.ucsd.edu/~mcoblenz/assets/pdf/OOPSLA_2025_PBT.pdf
- mkdocs-material: https://www.mkdocs.org/
- google-api-core retry: https://googleapis.dev/python/google-api-core/latest/retry.html
