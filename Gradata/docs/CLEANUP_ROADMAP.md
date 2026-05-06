## Section 1: Confirmed Redundancies (KEEP/MERGE/DELETE per pair)

### 1. Confidence / Graduation Spines

**Files**: `Gradata/src/gradata/enhancements/self_improvement/_confidence.py:1` + `_graduation.py:1` vs `Gradata/src/gradata/enhancements/graduation/scoring.py:1` vs `Gradata/src/gradata/enhancements/graduation/agent_graduation.py:1` vs `Gradata/src/gradata/enhancements/graduation/judgment_decay.py:1` vs `Gradata/src/gradata/enhancements/graduation/rules_distillation.py:1`

**Overlap %**: 65% conceptual overlap across the family, but uneven:
- `self_improvement/_confidence.py` + `_graduation.py` are the canonical live lesson engine: constants, FSRS/Bayesian confidence, parse/format, `update_confidence`, `graduate` (`_confidence.py:1-8`, `_confidence.py:639`, `_graduation.py:158`).
- `graduation/scoring.py` is an alternate opt-in blended scoring engine with its own feature dataclasses and thresholds (`scoring.py:1-11`, `scoring.py:36`, `scoring.py:54`, `scoring.py:104`, `scoring.py:196`). Overlap with `graduate()` is about 70%: same promotion decision domain, different formula.
- `agent_graduation.py` reuses self-improvement constants and Lesson model (`agent_graduation.py:41-55`) but persists agent profiles and gates approval behavior (`agent_graduation.py:70`, `agent_graduation.py:253`). Overlap with canonical lesson graduation is about 45%.
- `judgment_decay.py` is decay/reinforcement for unused lessons (`judgment_decay.py:2-19`, `judgment_decay.py:115`), about 40% overlap with kill/untestable behavior already in `_graduation.py:271-312`.
- `rules_distillation.py` is cross-lesson pattern proposal, explicitly distinct from individual lesson graduation (`rules_distillation.py:20-23`), about 25% overlap.

**Caller graph**:
- Canonical path is production live: `_core.py` imports `update_confidence` at `Gradata/src/gradata/_core.py:351` and calls it at `_core.py:611`, `_core.py:849`; `_core.py:863` calls `graduate`. `hooks/session_close.py:108` also calls `graduate`.
- Public API re-exports canonical symbols at `Gradata/src/gradata/__init__.py:51-55` and `__init__.py:93-98`.
- `graduation/scoring.py` is test-only in this checkout: `Gradata/tests/test_graduation_scoring.py:9-15`; no production callers found by `rg compute_graduation_score|should_graduate_lesson`.
- `agent_graduation.py` has tests at `Gradata/tests/test_agent_graduation.py:5-18` and spawn tests at `Gradata/tests/test_spawn_extraction.py:263-311`; production caller is `Brain.agent_profile()` at `Gradata/src/gradata/brain.py:1412`.
- `judgment_decay.py` is test-only by grep (`Gradata/tests/test_judgment_decay.py:16-24`, `:56-281`); no SDK production caller found.
- `rules_distillation.py` is test-only by grep (`Gradata/tests/test_rules_distillation.py:12-16`, `:49-198`); no SDK production caller found.

**Verdict**: MERGE / DELETE_ONE candidates.
- Keep `self_improvement/` canonical.
- Delete or quarantine `graduation/scoring.py` unless `GRADATA_AGENT_SCORING` is about to ship; it is an alternate decision spine with no production caller.
- Keep `agent_graduation.py` for now, but rename/package as `agents/` or `optional_agents/`; it is not the same graduation layer.
- Keep `judgment_decay.py` and `rules_distillation.py` only if they get wiring or move to `experimental/`.

**Migration steps**:
1. Add a deprecation note to `graduation/scoring.py`; remove `GRADATA_AGENT_SCORING` language unless integrated into `graduate()`.
2. Run verification before delete: `cd Gradata && rg "graduation'"\\.scoring|compute_graduation_score|should_graduate_lesson\" src tests && pytest tests/test_graduation_scoring.py tests/test_safety_assertion.py tests/test_enhancements.py"'`.
3. For `judgment_decay.py` and `rules_distillation.py`, either wire them through a CLI/API or move under `enhancements/experimental/` with import shims.

**Risk**: medium. Tests prove the alternates are alive, but production grep says only canonical is in the live loop.

**Files that would change**: `src/gradata/enhancements/graduation/scoring.py`, `tests/test_graduation_scoring.py`, maybe `src/gradata/enhancements/graduation/__init__.py`, `docs/changelog.md`.

### 2. Scoring Metrics vs Canonical Confidence

**Files**: `Gradata/src/gradata/enhancements/self_improvement/_confidence.py:1` vs `Gradata/src/gradata/enhancements/scoring/brain_scores.py:35` vs `scoring/correction_tracking.py:25` vs `scoring/calibration.py:30` vs `scoring/gate_calibration.py:26` vs `scoring/success_conditions.py:29` vs `scoring/reports.py:28` vs `_manifest_metrics.py:78`

**Overlap %**: 50% metric-domain overlap, 20% direct implementation overlap.
- Canonical confidence is per-lesson mutation (`_confidence.py:639`) with thresholds at `_confidence.py:46-56`.
- `brain_scores.py` computes aggregate scores (`brain_scores.py:35`, `brain_scores.py:188`).
- `correction_tracking.py` computes densities, half-life, MTBF/MTTR, and correction profiles (`correction_tracking.py:25`, `:185`, `:236`, `:291`, `:431`).
- `_manifest_metrics.py` separately computes `correction_rate` and trend (`_manifest_metrics.py:78`, `:304-367`). This overlaps with `correction_tracking.compute_density()` and `brain_scores` quality reporting.

**Caller graph**:
- `brain_scores` is imported by tests at `Gradata/tests/test_brain_scores.py:18` and by `scoring/brain_scores.py:25` from correction tracking.
- `correction_tracking` is tested at `Gradata/tests/test_correction_tracking.py:23` and imported by `brain_scores.py:25`.
- `calibration` and `gate_calibration` are test-heavy (`Gradata/tests/test_calibration_coverage.py:14`, `Gradata/tests/test_gate_calibration_coverage.py:14-25`) with no production caller found.
- `_manifest_metrics.py` is production-adjacent for manifests and computes its own correction rate (`_manifest_metrics.py:304`, `:355`, `:367`).

**Verdict**: KEEP_BOTH for confidence vs observability, MERGE for duplicate metric calculations.

**Migration steps**:
1. Move scoring modules into an explicit `observability` namespace or extra; keep canonical confidence untouched.
2. Make `_manifest_metrics.py` call a shared metric helper for `correction_rate` / trend instead of local formulas.
3. Run `pytest tests/test_brain_scores.py tests/test_correction_tracking.py tests/test_gate_calibration_coverage.py tests/test_manifest_prove.py`.

**Risk**: medium. Metrics are broad and test-heavy; the clean win is namespace clarity, not formula deletion.

**Files that would change**: `src/gradata/enhancements/scoring/*`, `src/gradata/_manifest_metrics.py`, `src/gradata/_manifest_quality.py`, tests listed above.

### 3. Four Synthesizer Modules

**Files**: `Gradata/src/gradata/enhancements/rule_synthesizer.py:1` vs `behavioral_extractor.py:1` vs `llm_synthesizer.py:1` vs `prompt_synthesizer.py:1` vs cloud proxy `gradata-cloud/cloud/app/routes/synthesize.py:1`

**Overlap %**:
- `rule_synthesizer.py` vs `prompt_synthesizer.py`: 35%. Both produce prompt text from rules, but `rule_synthesizer` calls Anthropic/Claude CLI to emit `<brain-wisdom>` (`rule_synthesizer.py:1-24`, `:155-252`), while `prompt_synthesizer` is deterministic anchor-preserving brain injection (`prompt_synthesizer.py:1-13`, `:175`, `:273`).
- `llm_synthesizer.py` vs cloud `/synthesize`: 90% prompt overlap. Cloud explicitly says it mirrors SDK format (`synthesize.py:157-162`) and the prompt body matches SDK (`llm_synthesizer.py:97-103`, `synthesize.py:164-170`).
- `behavioral_extractor.py` vs the other three: 20%. It extracts actionable instructions from draft/final diffs (`behavioral_extractor.py:1-18`, `:553-598`), not meta-rule/prompt synthesis.

**Caller graph**:
- `behavioral_extractor.extract_instruction` is live in `_core.py:384-388`; tests mock it at `tests/test_core_behavioral.py:17-53`.
- `behavioral_extractor.detect_recurring_patterns` is test-only at `tests/test_behavioral_extractor.py:4-61`.
- `llm_synthesizer.synthesise_principle_llm` is called from `meta_rules.py:925-933` and tested in `tests/test_llm_synthesizer.py:7-112` plus security tests.
- `prompt_synthesizer.classify_slot` is called during graduation at `_graduation.py:44-47`; both synthesis functions are tested at `tests/test_prompt_synthesizer.py:5-323`.
- `rule_synthesizer.synthesize_rules_block` appears test-only in this checkout (`tests/test_rule_synthesizer.py:10-107`); meta_rules docstring says LLM-assisted distillation is handled by `rule_synthesizer` (`meta_rules.py:25-27`), but actual code path uses `llm_synthesizer` and native Gemma (`meta_rules.py:887-943`).
- Cloud `/synthesize` has endpoint implementation at `synthesize.py:194-222`; no SDK client caller found in `src/` by grep.

**Verdict**: RENAME + MERGE.
- Rename `prompt_synthesizer.py` to `prompt_compactor.py` or `brain_injection_synthesizer.py`; it is not LLM synthesis.
- Merge prompt construction between `llm_synthesizer.py` and cloud `routes/synthesize.py` to one shared contract test or duplicated golden string.
- Delete or experimental-gate `rule_synthesizer.py` unless the injection hook actually calls it.

**Migration steps**:
1. Add a compatibility import shim for `prompt_synthesizer` and rename canonical module to reduce confusion.
2. Add golden prompt tests comparing SDK `llm_synthesizer` and cloud `_build_prompt`.
3. Before deleting `rule_synthesizer.py`: run `rg "rule_synthesizer|synthesize_rules_block" Gradata gradata-cloud` and `pytest tests/test_rule_synthesizer.py tests/test_prompt_synthesizer.py tests/test_llm_synthesizer.py`.

**Risk**: low for rename with shim; medium for deleting `rule_synthesizer.py` because docs reference it.

**Files that would change**: `src/gradata/enhancements/prompt_synthesizer.py`, `src/gradata/enhancements/rule_synthesizer.py`, `src/gradata/enhancements/meta_rules.py`, `gradata-cloud/cloud/app/routes/synthesize.py`, related tests.

### 4. Behavioral Registries

**Files**: `Gradata/src/gradata/enhancements/behavioral_engine.py:70` vs `Gradata/src/gradata/enhancements/meta_rules.py:55`

**Overlap %**: 55% conceptual overlap, 15% data-model overlap.
- `Directive`/`DirectiveRegistry` stores domain/task-triggered constraints with MUST/SHOULD/MAY priorities (`behavioral_engine.py:70-83`, `:116-229`).
- `MetaRule` stores emergent principles with source lessons, confidence, context weights, and source provenance (`meta_rules.py:55-84`).
- Both can format prompt-injected behavior (`behavioral_engine.py:196-229`, `meta_rules.py:513-586`), but they enter the system through different paths.

**Caller graph**:
- `Brain.__init__` creates `DirectiveRegistry` at `brain.py:153-155`; public methods delegate constraints at `brain.py:1896`.
- `DirectiveRegistry` is tested in `tests/test_spec_compliance.py:228-276`, `tests/test_adaptations.py:465-474`, and `tests/test_disposition.py:5`.
- `MetaRule` is heavily used by tests and storage: `tests/test_meta_rules.py:30-31`, `tests/test_agentic_synthesis.py:14-15`, `meta_rules_storage.py:33`, cloud route imports storage helpers at `gradata-cloud/cloud/app/routes/meta_rules.py:31-32`.

**Verdict**: KEEP_BOTH, but DOC_ONLY boundary clarification.

**Migration steps**:
1. Document: `DirectiveRegistry` = static/direct user contracts; `MetaRule` = learned emergent principles.
2. Add a small adapter only if prompt formatting needs a common interface; do not merge the dataclasses.
3. Run `pytest tests/test_spec_compliance.py tests/test_meta_rules.py tests/test_hooks_learning.py`.

**Risk**: low.

**Files that would change**: docs only, optionally `docs/architecture/overview.md` and `docs/sdk/rule-to-hook.md` (stale adapter wording at `docs/sdk/rule-to-hook.md:111`).

### 5. Session History Implementations

**Files**: `Gradata/src/gradata/services/session_history.py:1` vs `Gradata/src/gradata/integrations/session_history.py:1`

**Overlap %**: 100% by API, but `integrations` is a shim, not a second implementation.

**Caller graph**:
- Canonical service is imported by `Brain` at `brain.py:213-216` and tested at `tests/test_session_history.py:1`.
- Deprecated shim warns and re-exports everything (`integrations/session_history.py:1-19`). No production caller found; `rg` found only the shim itself and docs.

**Verdict**: DELETE_ONE later, not now. Keep shim through stated v0.9.0 unless this is a breaking release.

**Migration steps**:
1. Leave shim in v0.7.x; ensure changelog says removal target.
2. Before removal: `rg "integrations'"\\.session_history|from gradata.integrations.session_history\" Gradata gradata-cloud"'`.
3. Run `pytest tests/test_session_history.py tests/test_nervous_system_integration.py`.

**Risk**: low if removal waits for v0.9.0; medium if deleted in v0.7.x.

**Files that would change**: `src/gradata/integrations/session_history.py`, `docs/changelog.md`, tests only if adding deprecation assertions.

### 6. Deprecated `integrations/` vs Live Agent-Lightning

**Files**: `Gradata/src/gradata/integrations/__init__.py:1` vs `Gradata/src/gradata/integrations/agent_lightning/__init__.py:1` vs `Gradata/src/gradata/middleware/__init__.py:1`

**Overlap %**: 0% with middleware behavior, 80% namespace confusion.
- `integrations/__init__.py` says the namespace is deprecated and going away (`integrations/__init__.py:1-13`).
- `agent_lightning` is a live optional tuning integration (`agent_lightning/__init__.py:1-9`) and lazy-loads optional deps correctly (`agent_lightning/__init__.py:27-40`, `runner.py:102-129`, `litagent.py:19-38`).
- CLI imports `run_apo_tune` from integrations at `cli.py:510`; example imports it at `examples/tune_one_prompt.py:7`; tests import public integration at `tests/test_agent_lightning_bridge.py:20`.

**Verdict**: RENAME / MOVE before deleting `integrations/`.

**Migration steps**:
1. Move `integrations/agent_lightning` to `middleware/agent_lightning` or `tuning/agent_lightning`; leave `integrations.agent_lightning` shim through v0.9.0.
2. Update CLI import at `src/gradata/cli.py:510` and example `examples/tune_one_prompt.py:7`.
3. Run `pytest tests/test_agent_lightning_bridge.py tests/test_cli.py` plus `rg "gradata.integrations.agent_lightning"` before final removal.

**Risk**: medium. Deleting `integrations/` today breaks CLI/examples/tests.

**Files that would change**: `src/gradata/integrations/agent_lightning/*`, new target package, `src/gradata/cli.py`, `examples/tune_one_prompt.py`, `tests/test_agent_lightning_bridge.py`, docs.

## Section 2: God-Object Brain Split Proposal

`Brain` is 2,056 LOC and has 62 public methods by direct grep (`brain.py:58`, `brain.py:234-2011`). The premise says 70+, but this checkout has 62 non-underscore methods. Still too broad.

Proposed namespace splits with backward-compatible forwarding methods on `Brain`:

1. `brain.learning`: `correct`, `record_correction`, `patch_rule`, `auto_heal`, `add_rule`, `end_session`, `auto_evolve`, `detect_implicit_feedback`, `apply_brain_rules` (`brain.py:400`, `:467`, `:503`, `:558`, `:593`, `:743`, `:761`, `:783`, `:877`).
2. `brain.rules`: `scoped_rules`, `scope`, `plan`, `forget`, `rollback`, `lineage`, approval workflow, exports (`brain.py:997`, `:1029`, `:1053`, `:1075`, `:1168`, `:1239`, `:1335-1473`).
3. `brain.events`: `on_notification`, `emit`, `query_events`, `observe`, `search`, `get_facts` (`brain.py:1486`, `:1505`, `:1518`, `:1539`, `:1548`, `:1612`).
4. `brain.ops`: budgets, cloud/proof/stats/tree/health/tools/runtime helpers (`brain.py:298-306`, `:789-835`, `:1693-1887`, `:1896-2011`).

Keep `Brain` as facade for v0.7.x. First PR should only move method bodies to helper classes/modules and preserve exact public signatures.

## Section 3: Files Over 500 Lines (flag + suggest split target)

Production/source files over 500 LOC by `rg --files -g '"'*.py' | xargs wc -l"'`:

- `Gradata/src/gradata/_core.py:1` — 2,271 LOC. Split into `_core_learning.py`, `_core_session.py`, `_core_cloud.py`, `_core_metrics.py`.
- `Gradata/src/gradata/brain.py:58` — 2,056 LOC. Split as Section 2.
- `Gradata/src/gradata/cli.py:1` — 1,609 LOC. Split command groups: cloud, hooks, tune, inspect.
- `Gradata/src/gradata/enhancements/meta_rules.py:1` — 1,393 LOC. Split model/discovery/LLM/agentic synthesis; storage is already separate.
- `Gradata/src/gradata/enhancements/self_improvement/_confidence.py:1` — 1,218 LOC. Split parse/format from confidence math.
- `Gradata/src/gradata/daemon.py:1` — 979 LOC. Split routes/handlers from server boot.
- `Gradata/src/gradata/enhancements/rule_to_hook.py:1` — 932 LOC. Split classifier/generator/installer/demoter.
- `Gradata/src/gradata/enhancements/graduation/agent_graduation.py:1` — 887 LOC. Split profiles/outcomes/gates/deterministic rules.
- `Gradata/src/gradata/_events.py:1` — 867 LOC. Split JSONL/SQLite/query/bus.
- `Gradata/src/gradata/hooks/inject_brain_rules.py:1` — 846 LOC. Split ranking/rendering/I/O.
- `Gradata/src/gradata/_validator.py:1` — 769 LOC. Split validation domains.
- `Gradata/src/gradata/enhancements/meta_rules_storage.py:1` — 725 LOC. Split schema, CRUD, DP export.
- `Gradata/src/gradata/enhancements/rule_pipeline.py:1` — 692 LOC. Split orchestration from skill generation/review.
- `Gradata/src/gradata/enhancements/behavioral_extractor.py:1` — 691 LOC. Split archetype detection, instruction generation, recurring patterns.
- `Gradata/src/gradata/mcp_server.py:1` — 684 LOC. Split JSON-RPC dispatch from tools.
- `Gradata/src/gradata/mcp_tools.py:1` — 643 LOC. Split tool groups.
- `Gradata/src/gradata/correction_detector.py:1` — 643 LOC. Split detection modes/conflicts/extraction.
- `Gradata/src/gradata/enhancements/scoring/loop_intelligence.py:1` — 633 LOC. Split logging, stats, markdown writer.
- `Gradata/src/gradata/enhancements/pattern_integration.py:1` — 630 LOC. Split adapters by pattern type.
- `Gradata/src/gradata/enhancements/self_healing.py:1` — 621 LOC. Split detection and patch application.
- `gradata-cloud/cloud/app/routes/billing.py:1` — 610 LOC. Split checkout/portal/webhooks/subscription state.
- `Gradata/src/gradata/enhancements/edit_classifier.py:1` — 604 LOC. Split token utilities/classifier/templates.
- `Gradata/src/gradata/sidecar/watcher.py:1` — 593 LOC. Split watch loop/sync/retry.
- `Gradata/src/gradata/contrib/enhancements/install_manifest.py:1` — 571 LOC. Split manifest I/O/resolution/install.
- `Gradata/src/gradata/rules/rule_engine/_engine.py:1` — 551 LOC. Split filtering/scoring/render handoff.
- `Gradata/src/gradata/rules/scope.py:1` — 549 LOC. Split parsing/matching/export.
- `Gradata/src/gradata/_manifest_quality.py:1` — 547 LOC. Split simulation/scoring/report.
- `Gradata/src/gradata/_doctor.py:1` — 542 LOC. Split checks by subsystem.
- `Gradata/src/gradata/_manifest_metrics.py:1` — 525 LOC. Split metric collection from synthesis.
- `Gradata/src/gradata/rules/rule_engine/_formatting.py:1` — 514 LOC. Split XML rendering/grouping.
- `Gradata/src/gradata/enhancements/diff_engine.py:1` — 512 LOC. Split diff stats/severity/semantic optional path.
- `Gradata/src/gradata/onboard.py:1` — 509 LOC. Split interactive flow from file writes.

Test files over 500 LOC are numerous; do not split unless they block review ergonomics. Highest offenders: `tests/test_adaptations.py:1` at 2,661 LOC, `tests/test_patterns.py:1` at 1,539 LOC, `tests/test_rule_to_hook.py:1` at 1,459 LOC.

## Section 4: Dead Code Candidates (with verification grep)

1. `src/gradata/enhancements/graduation/scoring.py:1` — alternate opt-in scoring, no production caller found; tests only at `tests/test_graduation_scoring.py:9-15`. Verification: `rg "graduation'"\\.scoring|compute_graduation_score|should_graduate_lesson\" Gradata/src Gradata/tests"'` then `pytest tests/test_graduation_scoring.py tests/test_safety_assertion.py`.
2. `src/gradata/enhancements/rule_synthesizer.py:1` — doc says injection hook synthesis, but grep found tests only (`tests/test_rule_synthesizer.py:10-107`) and no production caller. Verification: `rg "rule_synthesizer|synthesize_rules_block" Gradata/src Gradata/tests` then `pytest tests/test_rule_synthesizer.py tests/test_hooks_learning.py`.
3. `src/gradata/enhancements/graduation/judgment_decay.py:1` — pure algorithm, tests only (`tests/test_judgment_decay.py:16-281`), no production caller found. Verification: `rg "judgment_decay|compute_decay|compute_batch_decay" Gradata/src Gradata/tests`.
4. `src/gradata/enhancements/graduation/rules_distillation.py:1` — pure algorithm, tests only (`tests/test_rules_distillation.py:12-198`), no production caller found. Verification: `rg "rules_distillation|find_distillation_candidates" Gradata/src Gradata/tests`.
5. `gradata-cloud/cloud/app/routes/synthesize.py:1` — implemented endpoint, but no SDK client caller found. Keep if planned paid feature; otherwise it is cloud-only dead surface. Verification: `rg "POST /synthesize|/synthesize|synthesize_principle" Gradata gradata-cloud` plus route registration check.
6. `integrations/session_history.py:1` — not dead, deprecated shim. Delete only at v0.9.0 after `rg "integrations'"\\.session_history\""'` is clean.
7. `integrations/agent_lightning/*` — not dead: tests (`tests/test_agent_lightning_bridge.py:20`), CLI (`cli.py:510`), and example (`examples/tune_one_prompt.py:7`) prove alive. Must move before `integrations/` deletion.
8. `__pycache__` stale pyc files — none found. Verification command returned empty: `rg --files -g '"'*.pyc' Gradata gradata-cloud"'`.
9. Stale comments referencing flat `self_improvement.py`: examples include `docs/system-architecture.md:312`, `docs/superpowers/specs/2026-04-11-hierarchical-rule-tree-design.md:181`, `src/gradata/enhancements/rule_export.py:27`, `src/gradata/enhancements/rule_context_bridge.py:10`. These are doc/comment cleanup, not runtime dead code.
10. `docs/sdk/rule-to-hook.md:111` says adapters in `gradata.integrations.*` build system prompts; current middleware docs point to `gradata.middleware` (`docs/changelog.md:12`, `src/gradata/middleware/__init__.py:11-25`). Stale doc.

TODO age: no TODO older than 30 days was verified by blame. Oldest inspected TODOs are 2026-04-13/14: `_core.py:2015`, `gradata-cloud/cloud/app/routes/operator.py:160`, `operator.py:331`, `gdpr.py:254`, `gdpr.py:307`. Current date is 2026-05-06, so these are under 30 days by blame.

## Section 5: Optional Imports That Should Move To Call Site

Mostly good: optional SDK deps are call-site gated.

- `middleware/anthropic_adapter.py:41` and `middleware/openai_adapter.py:36` validate optional deps inside constructors/helpers, not package import. Good.
- `_embed.py:173`, `_doctor.py:57`, `diff_engine.py:271` import `sentence_transformers` inside functions. Good.
- `integrations/agent_lightning/runner.py:104-107`, `runner.py:122`, `litagent.py:21`, `litagent.py:32` gate optional deps at call sites. Good.
- `rule_synthesizer.py:222` imports `anthropic` only when `ANTHROPIC_API_KEY` exists. Good.
- `enhancements/llm_provider.py:132` and `:160` import provider SDKs inside provider call paths. Good.

Potential issue:
- `gradata-cloud/cloud/app/routes/synthesize.py:31` imports `httpx` at module import. In cloud this is fine because FastAPI app depends on `httpx` broadly (`cloud/app/auth.py:9`, `cloud/app/db.py:9`). If this route is optional in some deployment profile, move `httpx` into `_call_gemma`; otherwise no change.

## Section 6: Top 10 Cleanups Ranked By ROI/Risk

1. **Rename `prompt_synthesizer.py`** to remove ambiguity. ROI high, risk low with shim.
2. **Quarantine or remove `graduation/scoring.py`**. ROI high, risk medium; alternate graduation spine confuses the canonical FSRS path.
3. **Move `agent_lightning` out of `integrations/` with shim**. ROI high, risk medium; unlocks future integrations deletion without breaking CLI/tests.
4. **Deduplicate SDK/cloud synthesis prompt**. ROI high, risk low; prompt drift is already admitted at `synthesize.py:157-162`.
5. **Split `Brain` facade internally**. ROI high, risk medium; preserve public API while shrinking review surface.
6. **Split `_core.py` by responsibility**. ROI high, risk medium-high because live correction/session flow is sensitive.
7. **Move scoring observability into explicit namespace/extra**. ROI medium-high, risk medium; reduce confidence-vs-metrics confusion.
8. **Wire or mark experimental `judgment_decay.py` and `rules_distillation.py`**. ROI medium, risk low.
9. **Clean stale docs/comments referencing flat `self_improvement.py` and `integrations.*` adapters**. ROI medium, risk low.
10. **Split large route files, starting with cloud `billing.py`**. ROI medium, risk low-medium.

## Section 7: Cleanup PR Roadmap (3-4 small PRs that don'"'t conflict)

### PR 1 — Naming + Docs Only

- Rename or shim "'`prompt_synthesizer` to clearer name.
- Update stale docs: `docs/sdk/rule-to-hook.md:111`, flat `self_improvement.py` comments, `docs/changelog.md:42-43` if needed.
- Tests: `pytest tests/test_prompt_synthesizer.py tests/test_slot_graduation.py`.

### PR 2 — Integrations Namespace Escape Hatch

- Move `integrations/agent_lightning` to `tuning/agent_lightning` or `middleware/agent_lightning`.
- Leave import shim at old path.
- Update `src/gradata/cli.py:510`, `examples/tune_one_prompt.py:7`, tests.
- Tests: `pytest tests/test_agent_lightning_bridge.py tests/test_cli.py`.

### PR 3 — Graduation Spine Reduction

- Mark `graduation/scoring.py` experimental/deprecated or remove after grep.
- Decide whether `judgment_decay.py` and `rules_distillation.py` are wired or moved to experimental.
- Tests: `pytest tests/test_graduation_scoring.py tests/test_judgment_decay.py tests/test_rules_distillation.py tests/test_safety_assertion.py tests/test_enhancements.py`.

### PR 4 — Brain Facade Internal Split

- Extract `Brain` method groups into internal collaborators without changing signatures.
- Start with low-risk ops/events methods (`emit`, `query_events`, `search`, exports) before learning/session mutation.
- Tests: `pytest tests/test_brain.py tests/test_brain_events.py tests/test_cli.py tests/test_mcp_server.py`.
EOF
printf '"'