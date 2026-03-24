# Architecture Patterns: Production SDK Layer

**Domain:** Python SDK production hardening
**Researched:** 2026-03-24

## Recommended Architecture Addition: Exception + Observability Boundary

The existing architecture (event-sourced SQLite, pattern modules, optional deps) is sound. What's missing is a **boundary layer** between the SDK internals and the consumer.

### Component Boundaries (Current + Proposed)

| Component | Responsibility | Status |
|-----------|---------------|--------|
| `brain.py` | Core Brain class, orchestration | EXISTS |
| `_events.py` | Event sourcing, SQLite writes | EXISTS |
| `_migrations.py` | Schema evolution | EXISTS |
| `patterns/` | Agentic patterns (15 modules) | EXISTS |
| `enhancements/` | CARL, quality gates, corrections | EXISTS |
| `_exceptions.py` | **Exception hierarchy + error codes** | PROPOSED |
| `_logging.py` | **Structured logging setup** | PROPOSED |
| `_deprecation.py` | **Deprecation utilities** | PROPOSED |
| `_compat.py` | **Version negotiation** | PROPOSED (v2.0) |

### Proposed Exception Architecture

```
src/aios_brain/_exceptions.py
    BrainError(Exception)
        code: str           # "BRAIN_NOT_FOUND", "EMBED_FAILED", etc.
        details: dict       # machine-readable context

    BrainNotFoundError(BrainError)       # brain_dir doesn't exist
    BrainCorruptedError(BrainError)      # db corruption, missing tables
    ConfigurationError(BrainError)       # invalid config values
    DependencyError(BrainError)          # optional dep not installed
    ValidationError(BrainError)          # input validation failures
    EmbeddingError(BrainError)           # embed/search operation failures
    ExportError(BrainError)              # export/install failures
    MigrationError(BrainError)           # schema migration failures
    PatternError(BrainError)             # pattern execution failures
```

### Proposed Logging Architecture

```python
# src/aios_brain/_logging.py
import logging
import os

def setup_logging() -> None:
    """Configure SDK logging from AIOS_BRAIN_LOG env var."""
    level = os.environ.get("AIOS_BRAIN_LOG", "warning").upper()
    logging.getLogger("aios_brain").setLevel(getattr(logging, level, logging.WARNING))

# Called from __init__.py at import time
# Every module uses: logger = logging.getLogger(__name__)
```

This matches how OpenAI SDK does it: `_setup_logging()` at import, env var for level.

## Patterns to Follow

### Pattern 1: Lazy Optional Dependencies (Already Implemented)
**What:** Check optional deps at method call time, not import time.
**Status:** Already done correctly in `brain.py` with `_require_chromadb()`.
**Keep as-is.**

### Pattern 2: Exception Wrapping at Boundaries
**What:** Catch internal exceptions and wrap in SDK-specific types at public method boundaries.
**When:** Every public method on `Brain` class.
**Example:**
```python
def search(self, query: str, ...) -> list:
    try:
        return self._search_impl(query, ...)
    except ImportError as e:
        raise DependencyError("chromadb", str(e)) from e
    except sqlite3.OperationalError as e:
        raise BrainCorruptedError(str(e)) from e
    except Exception as e:
        raise BrainError(f"Search failed: {e}") from e
```

### Pattern 3: Structured Logging Convention
**What:** Every significant operation logs at DEBUG with context.
**When:** Brain init, search, embed, correct, export, migrate.
**Example:**
```python
logger.debug("brain.search", extra={"query": query[:50], "mode": mode, "brain_dir": str(self.dir)})
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Catching Too Broadly
**What:** `except Exception: pass` in SDK code.
**Why bad:** Swallows errors users need to see.
**Instead:** Catch specific exceptions, re-raise as typed BrainError.

### Anti-Pattern 2: Logging at Wrong Level
**What:** Using `logger.info()` for routine operations.
**Why bad:** Pollutes user's application logs.
**Instead:** DEBUG for routine, WARNING for recoverable issues, ERROR only for failures. SDK should be silent at INFO level by default.

### Anti-Pattern 3: Breaking Public API Without Deprecation
**What:** Renaming a method or changing a return type.
**Why bad:** External users' code breaks silently.
**Instead:** Keep old name as deprecated alias for 2 minor versions.

## Data Flow: Error Propagation

```
User calls brain.search("query")
  -> Brain.search() [public boundary]
    -> _require_chromadb() [dep check]
      -> raises DependencyError if missing
    -> self._search_impl() [internal]
      -> chromadb.Collection.query() [external]
        -> sqlite3 error or chromadb error
      -> caught, wrapped as EmbeddingError
    -> logger.debug("search complete", extra={...})
  -> returns results or raises BrainError subclass
```

## Sources

- OpenAI SDK logging: https://github.com/openai/openai-python (src/openai/_utils/_logs.py)
- Stripe SDK errors: https://github.com/stripe/stripe-python/blob/master/stripe/_error.py
- google-cloud-python exceptions: https://googleapis.dev/python/google-api-core/latest/retry.html
