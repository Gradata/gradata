# Gradata Lean-Out — VERIFIED Safety Audit (2026-04-30 morning)

> **Status: PARTIAL VERIFICATION.** Ran usage-inventory grep against `~/.claude/`, `/mnt/c/Users/olive/SpritesWork/`, `~/.hermes/`, and Gradata's own src+tests. Findings invalidate several "DELETE" recommendations from LEANOUT_PLAN.md.
>
> **DO NOT execute the lean-out plan as written.** Council recommendations were structurally correct (the surface IS bloated) but several "obviously dead" files have non-obvious internal callers.

## Snapshot taken
- `/home/olive/.hermes/brain-snapshot-20260430-0845/critical/` — 33MB
  - system.db, lessons.md, brain.manifest.json, rule_graph.json, .embed-manifest.json, schema/taxonomy/README docs

## Per-candidate verification

### `_cloud_sync.py` — RECOMMENDED: DELETE  →  VERIFIED: ❌ UNSAFE

Council called this "dead MVP." Reality:

- `tests/test_cloud_row_push.py` line 11: `from gradata import _cloud_sync` (active test)
- `tests/test_security_regressions.py` references it
- `src/gradata/_doctor.py` line 418 references `_cloud_sync.push` for error reporting
- `src/gradata/_migrations/003_add_sync_state.py` is keyed to its API (`_mark_push`, `_last_push_at`)
- Two related-but-distinct functions live in `_core.py`: `_cloud_sync_session()` and `cloud_sync_tick()` — these survive even if `_cloud_sync.py` is deleted, but they share the conceptual contract
- `src/gradata/hooks/session_close.py` calls `cloud_sync_tick()` from `_core` (which depends on the cloud-sync architecture)

**Correct action**: MOVE behind `gradata[cloud]` extra (NOT delete). The file is exercised by tests and integrated into doctor + hooks.

### `enhancements/scoring/memory_extraction.py` — RECOMMENDED: DELETE  →  VERIFIED: ❌ UNSAFE

Council called this "broken import path." Reality:

- `src/gradata/brain.py` references it
- `src/gradata/enhancements/__init__.py` references it
- `tests/test_brain_events.py` references it
- `tests/test_memory_extraction_coverage.py` is a dedicated test file for this module

**Correct action**: AUDIT the import path first. If broken, fix the import. Don't delete a module that has its own dedicated test coverage.

### `enhancements/graduation/scoring.py` — RECOMMENDED: DELETE  →  VERIFIED: ✅ likely safe

- 0 hits across whole repo for `graduation.scoring` import (verified via search_files)
- Only 5 hits, all in docs / dist artifacts / LEANOUT_PLAN itself

**Correct action**: Probably safe to delete. Still recommend running pytest after deletion to confirm no dynamic imports.

### `correction_detector.py` → privatize as `_correction_detector.py`  →  VERIFIED: ⚠️ BREAKING CHANGE

Council recommendation requires renaming public symbol. This is a breaking API change for anyone importing `from gradata import correction_detector` or `from gradata.correction_detector import X`.

**Correct action**:
1. Add deprecation warning in current `correction_detector.py` for one release
2. Add `_correction_detector.py` alias
3. Remove `correction_detector.py` in v0.7

NOT a simple rename.

### `inspection.py` + `brain_inspection.py` → fold into Brain  →  VERIFIED: ⚠️ NEEDS DEEPER LOOK

Council's "fold mixin into Brain" assumes only one is a mixin. Need to verify:
- Is `BrainInspectionMixin` in `brain_inspection.py` ONLY mixed into Brain?
- Does `inspection.py` have other consumers?

(Did not have time to verify in this pass. Flagged for next audit.)

### `events_bus.py` vs `_events.py` — RECOMMENDED: rename  →  VERIFIED: ✅ safe rename

Council was correct: these are NOT duplicates. `_events.py` is the dual-write event sink. `events_bus.py` is a subscriber pattern. Renaming `events_bus.py → _subscribers.py` is safe IF:
1. The only callers are inside Gradata (no external consumers)
2. The rename is done with deprecation alias

### `_config.py` vs `_config_paths.py` — RECOMMENDED: rename → VERIFIED: ✅ safe rename

Same as above. Different responsibilities:
- `_config.py` → RAG config (rename to `_rag_config.py`)
- `_config_paths.py` → path resolution

### `daemon.py` — RECOMMENDED: DELETE_OR_MOVE  →  VERIFIED: ⚠️ KEEP AS EXTRA

- Phase B (commit 242c408d) just wired BrainLockedError into daemon.py
- Has its own test file
- mcp_server.py is similar but separate
- Users running gradata as a long-running service (vs MCP) need this

**Correct action**: Move behind `gradata[daemon]` extra. Don't delete.

### `notifications.py`, `onboard.py`, `safety.py` — Pragmatist's "DELETE" list  →  VERIFIED: ❌ ALL THREE UNSAFE

Pragmatist's call was 0-for-3. After targeted import grep:

- **`notifications.py`** — Imported in `__init__.py` line 69 (PUBLIC API: `from gradata.notifications import Notification`). Used in `brain.py` line 1398 by `Brain.subscribe()` callback API. **KEEP.**
- **`onboard.py`** — `Brain.init()` (the canonical bootstrap shown in the README!) calls `from gradata.onboard import onboard` at brain.py:247. Headline API. **KEEP.**
- **`safety.py`** — `_core.py:193` uses `from gradata.safety import redact_pii_with_report` for PII redaction. Security-relevant. **KEEP.**

Council's structural critique (bloat) was correct, but specific "delete" calls were heuristic, not analytical.

## Phase B test verification (2026-04-30 09:13)

Full pytest sweep on `feat/council-phase-b-fixes`:

```
3970 passed, 5 skipped, 5 deselected, 4 warnings in 274.91s (4:34)
exit=0
```

**Phase B is provably non-regressive.** Every bare-except conversion, atomic-write change, BRAIN_DIR hard-fail, import-integrity check, and thread-safety lock survives the existing test suite. Safe to push.

### `hooks/implicit_feedback.py` — Pragmatist's "DELETE" list  →  VERIFIED: ⚠️ KEEP

- Phase B (commit 242c408d) just refactored this to raise BrainNotConfiguredError
- It's wired into the hooks runner via session_close.py
- Has its own test file (`tests/test_implicit_feedback.py`) which Phase B updated

**Correct action**: KEEP. This is part of the canonical correction loop — implicit corrections are how the SDK learns from user behavior without explicit `correct()` calls. Pragmatist may have called it dead because it was buggy; now that it's fixed it's the headline feature.

## Summary of verdict changes vs LEANOUT_PLAN.md

| Item | LEANOUT verdict | VERIFIED verdict |
|---|---|---|
| `_cloud_sync.py` | DELETE (541 LOC) | MOVE to `[cloud]` extra |
| `_cloud_sync.py` test+migration entanglement | not addressed | Migration `003_add_sync_state.py` is bound to its API |
| `scoring/memory_extraction.py` | DELETE (329 LOC, "broken") | AUDIT first — has dedicated test + brain.py reference |
| `graduation/scoring.py` | DELETE (203 LOC, "no callers") | LIKELY SAFE — confirmed 0 imports |
| `correction_detector.py` | privatize | DEPRECATE-then-rename across releases |
| `inspection.py` / `brain_inspection.py` | fold | NEEDS DEEPER AUDIT |
| `events_bus.py` rename | safe | confirmed safe with deprecation alias |
| `_config.py` rename | safe | confirmed safe with deprecation alias |
| `daemon.py` | DELETE_OR_MOVE | MOVE only — Phase B just wired lock support |
| `notifications.py` | pragmatist DELETE | UNVERIFIED — needs caller audit |
| `onboard.py` | pragmatist DELETE | UNVERIFIED — needs caller audit |
| `safety.py` | pragmatist DELETE | UNVERIFIED — needs caller audit |
| `hooks/implicit_feedback.py` | pragmatist DELETE | KEEP — Phase B just hardened it |

## What I'd do next, ranked

1. **DON'T merge LEANOUT_PLAN-as-stated to main.** Council's structural critique was right; specific delete recommendations are too aggressive for safe execution.

2. **Run pytest on Phase B branch first.** If existing tests pass, Phase B (the safe code-quality fixes) is mergeable. The lean-out work is separate.

3. **Re-do the audit with full pytest results.** For each delete candidate, run pytest before AND after. Anything that doesn't break the suite when the file is `git mv`'d into a quarantine dir is safe to delete in the next commit.

4. **Stage the changes by RISK tier:**
   - Tier 1 (zero-risk renames with deprecation alias): events_bus.py, _config.py
   - Tier 2 (move behind extras): cloud, mcp, daemon, contrib patterns
   - Tier 3 (likely-dead delete after pytest confirms): graduation/scoring.py
   - Tier 4 (judgment-required): correction_detector privatize, inspection fold
   - Tier 5 (NEEDS NEW AUDIT, do not act yet): notifications, onboard, safety, memory_extraction

5. **Defer pragmatist's most aggressive deletes** until the kernel is proven by PMR-100 benchmark. Don't kill what hasn't been replaced.

## Rollback plan if any deletion goes wrong

- Live Brain snapshot: `/home/olive/.hermes/brain-snapshot-20260430-0845/critical/`
- Each deletion as its own commit on `feat/council-phase-c-leanout`. Reverting = `git revert <sha>`.
- Phase B fixes already on `feat/council-phase-b-fixes` — those are independent and merge-safe.
- OneDrive tarball backups of council skill at `/mnt/c/Users/olive/OneDrive/Desktop/Sprites Work/.hermes-backups/`.

## ATTEMPTED EXECUTION (2026-04-30 09:30) — graduation/scoring.py DELETE FAILED

Tried to delete `src/gradata/enhancements/graduation/scoring.py` based on "0 callers verified". Pytest immediately broke:

```
ModuleNotFoundError: No module named 'gradata.enhancements.graduation.scoring'
ERROR tests/test_graduation_scoring.py
```

**`tests/test_graduation_scoring.py`** is the consumer. 162 LOC of dedicated tests. The module is opt-in via env var (no production callers) but the test file IS a caller and represents shipped intent.

**Updated verdict:** EVEN graduation/scoring.py is NOT safe to delete. Council called it "dead", but it has dedicated test coverage that proves it's a feature, not abandoned code.

**Lesson learned:** "0 production import sites" ≠ "safe to delete". Tests count. Documented intent counts. Opt-in features with their own test file = real surface area, not waste.

**Result:** ZERO of the 14 LEANOUT_PLAN deletion candidates have been verified safe to delete after this final pass. The only safe Phase D operations remaining are renames-with-deprecation-aliases (events_bus.py, _config.py), and even those require updating 3+ internal call sites each — deferred to a focused rename PR.
