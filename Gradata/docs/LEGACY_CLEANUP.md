# Legacy Cloud-Gate Cleanup Tracker

As of 2026-04-20, Gradata is fully local-first. Cloud-gate stubs and
"cloud-only" fallbacks are legacy concepts that should be removed.

## Principle

- Every feature must run locally with no external service.
- `gradata_cloud_backup/` is a private backup, not a gate.
- LLM-assisted synthesis uses the user's own provider (Anthropic SDK key or
  Claude Code Max OAuth via `claude -p`). Never a Gradata-hosted endpoint.
- Tests and fixtures should exercise the local implementation directly.

## Known legacy items to retire

### 1. Deprecated adapter shims (scheduled v0.8.0)
- `src/gradata/integrations/anthropic_adapter.py` → `middleware.wrap_anthropic`
- `src/gradata/integrations/langchain_adapter.py` → `middleware.LangChainCallback`
- `src/gradata/integrations/crewai_adapter.py` → `middleware.CrewAIGuard`
Warnings are in place; remove the modules and their tests at v0.8.0.

### 2. `_cloud_sync.py` terminology
File posts to an optional external dashboard — fine to keep, but the
module docstring should make clear it is optional telemetry, not a
mandatory cloud dependency. Callers already tolerate absence.

### 3. Docstring drift in `meta_rules.py`
Module header still says "require Gradata Cloud" and "no-ops in the
open-source build". That is no longer true as of the local-first port —
rewrite the header to describe the local clustering algorithm.

### 4. Test-level cloud gating
Former `@_requires_cloud` / `skipif` markers were deleted in this cycle.
If any new test reintroduces a cloud gate, delete the gate instead — the
feature should either be local-first or not ship.

### 5. `api_key` kwarg on `merge_into_meta`
The old `merge_into_meta(..., api_key=...)` path routed into
`synthesise_principle_llm` directly. Current architecture drives LLM
distillation from `rule_synthesizer` at session close instead. The kwarg
is still accepted via `**kwargs` for forward compatibility but performs
no work — remove after one release.

### 6. Doc sweep
`docs/cloud/` should be audited for pages that imply cloud is required.
Rewrite as "optional managed hosting" or delete.

## How to retire an item

1. Grep for the symbol / doc string.
2. Delete the code path and any tests that exercise it.
3. Update the module docstring.
4. Bump the deprecation note in `CHANGELOG`.
5. Run the full suite.
