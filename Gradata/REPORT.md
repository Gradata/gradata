# Council Phase B Fix Report

## Status

Stopped during P0-2 because the sandbox cannot write to the repository metadata needed
to create commits.

- Branch observed: `feat/council-phase-b-fixes`.
- P0-2 code changes are present in the working tree but are not committed.
- Commit blocker: `git add` failed with `Unable to create '../.git/index.lock': Read-only file system`.
- Cause: this session can write inside `Gradata/`, but the Git directory lives one level
  up in `Sprites Work/.git`, outside the writable root.

## What Was Fixed In The Working Tree

### P0-2: Replace silent `except: pass` handlers

Implemented in the working tree only.

- Added `tests/test_no_bare_excepts.py`.
- The test scans `src/gradata/` with `ast` and rejects any single-statement
  `except ...: pass` handler unless it is a documented optional dependency
  `ImportError` probe.
- Converted non-allowlisted single-pass handlers to
  `logger.warning(..., exc_info=True)`.
- Added `logging` imports and `logger = logging.getLogger(__name__)` where needed.
- Scope used: 57 existing `src/gradata/` files plus the new AST regression test,
  within the approved 60-file / 800-LOC cap.

## Verification

Passing:

```bash
python3 - <<'PY'
import tests.test_no_bare_excepts as t
t.test_no_single_statement_except_pass_handlers()
print("AST regression passed")
PY

python3 -m compileall -q src/gradata tests/test_no_bare_excepts.py
```

Blocked:

```bash
pytest -xvs tests/test_no_bare_excepts.py
```

`pytest` is not installed on system Python. `uv run pytest -xvs tests/test_no_bare_excepts.py`
could not create the environment because network access is blocked while resolving PyPI
dependencies.

## What Was Not Committed

The requested commit was not created:

```text
fix(council-p0-2): replace silent except:pass with logged exceptions
```

The sandbox prevented `git add`, so no commit could be made.

## What Remains

Not started because each fix must land as its own commit and P0-2 cannot be committed
from this sandbox:

- P0-5: `rule_graph.json` atomic writes.
- P0-4: BRAIN_DIR-unresolved hard-fail with `BrainNotConfiguredError`, surfaced in
  `gradata doctor`.
- P0-7: package import integrity check.
- P0-6: thread-safety `fcntl` lock in `BRAIN_DIR/.brain.lock` for `daemon.py` and
  `mcp_server.py`.

## Next Required Action

Run the commit from an environment that can write to `Sprites Work/.git`, or adjust the
writable root so this agent can write the repository metadata. After P0-2 is committed,
resume with P0-5 in the requested order.
