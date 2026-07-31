# GRA-22 audit-report: graduation pipeline noise filtering, scoring, dedup

Scope: read-only audit of `/home/olive/work/gradata-sdk/Gradata` because the issue path `~/gradata/Gradata/` was not present as a SDK checkout. No repo files were changed.

## Executive summary

The spine is present but split across three paths:

1. Capture path: `PostToolUse` hooks call `gradata.hooks.auto_correct`, which extracts draft/final and calls `Brain.correct()`.
2. Correction-to-lesson path: `Brain.correct()` emits `CORRECTION`, dedups exact observations, creates/reinforces a `Lesson`, updates confidence, and writes `lessons.md`.
3. Graduation path: `Stop` hook `session_close` gates on new events, runs `_run_graduation()` and `run_rule_pipeline()`, then writes updated lessons. AGENTS.md export exists in `rule_export.py`, but the session-close path does not call `export_rules(target="agents")` or write AGENTS.md.

Most important finding: AGENTS.md write is not in the end-to-end Stop waterfall in this checkout. `session_close.main()` runs graduation, pipeline, tree consolidation, pending application resolution, and cloud sync only; export is separate CLI/library code.

## End-to-end path with file:line citations

| Stage | Evidence |
|---|---|
| Hook install command points PostToolUse to auto_correct | `src/gradata/hooks/adapters/_base.py:139-149` builds `python -m gradata.hooks.auto_correct` and `python -m gradata.hooks.session_close`; `src/gradata/hooks/adapters/claude_code.py:65-110` installs PostToolUse and Stop entries. |
| PostToolUse capture | `src/gradata/hooks/auto_correct.py:39-44` declares `PostToolUse` matcher `Edit|Write`; `auto_correct.py:66-96` adapter-dispatches payload extraction; `auto_correct.py:247-263` calls `brain.correct(draft, final)`. |
| Brain.correct validation and event emit | `src/gradata/_core.py:91-107` defines `brain_correct`; `src/gradata/_core.py:108-121` rejects empty/identical/invalid-session corrections; `src/gradata/_core.py:151-188` computes diff/classifications/category; `src/gradata/_core.py:268-308` builds and emits the `CORRECTION` event. |
| Observation dedup seam | `src/gradata/_core.py:329-341` calls `annotate_event_with_dedup`; `src/gradata/enhancements/dedup.py:236-270` fingerprints `(draft[:500], final[:500], category)` and returns duplicate status. |
| Lesson create/reinforce | `src/gradata/_core.py:356-365` opens/parses `lessons.md`; `src/gradata/_core.py:421-435` finds similar existing lesson; `src/gradata/_core.py:444-469` reinforces existing lesson; `src/gradata/_core.py:510-522` creates a new INSTINCT lesson; `src/gradata/_core.py:617-630` calls `update_confidence()` and writes lessons safely. |
| Confidence scoring | `src/gradata/enhancements/self_improvement/_confidence.py:651-712` defines update behavior; `:719-745` poisoning/machine/severity setup; `:789-893` reinforcement/contradiction/misfire scoring; `:950-975` per-session delta cap; `:1002-1020` inline promotion/demotion. |
| Stop hook gating | `src/gradata/hooks/session_close.py:38-42` declares `Stop`; `:46-54` lists trigger event types; `:72-95` checks new triggers; `:317-340` runs the Stop waterfall. |
| Graduation pass | `src/gradata/hooks/session_close.py:97-110` loads `lessons.md`, calls `graduate(lessons)`, writes active lessons; `src/gradata/enhancements/self_improvement/_graduation.py:165-193` defines the graduation state-machine. |
| Rule pipeline pass | `src/gradata/hooks/session_close.py:148-170` calls `run_rule_pipeline`; `src/gradata/enhancements/rule_pipeline.py:274-295` defines the 3-phase pipeline; `:430-443` calls canonical `_graduate`; `:445-468` synthesizes meta-rules; `:480-499` promotes deterministic hooks. |
| AGENTS.md export implementation | `src/gradata/enhancements/rule_export.py:24-58` selects RULE-tier lessons; `:70-93` formats grouped markdown; `:147-153` maps `agents` to `AGENTS.md`; `:157-167` exposes `export_rules()`. |
| AGENTS.md export gap | `src/gradata/hooks/session_close.py:317-340` never calls `rule_export.export_rules()` and never writes `AGENTS.md`. `src/gradata/cli.py:336` is the separate CLI export path, not the Stop/post-graduation flow. |

## Filter / score / dedup gates

| Gate | Current behavior | Evidence |
|---|---|---|
| Empty/no-op correction validation | Rejects empty draft+final and identical draft/final before event creation. | `src/gradata/_core.py:108-121`; synthetic output below. |
| Input size | Rejects combined draft+final over 100,000 chars. | `src/gradata/_core.py:115-119`. |
| PII redaction | Redacts draft/final before storage when safety module imports. | `src/gradata/_core.py:191-198`. |
| Provenance / adversarial phrases | Untrusted provenance or adversarial phrases sets `approval_required=True`, seeding new lesson at 0.0 and pending approval. | `src/gradata/_core.py:213-252`, `:510-522`, `:556-589`. |
| Observation dedup | Fingerprints exact `(draft, final, category)` text and skips lesson create/reinforce when duplicate. | `src/gradata/_core.py:329-341`, `src/gradata/enhancements/dedup.py:236-270`. |
| Similar lesson merge | For non-deduped observations, semantic/category similarity can reinforce an existing lesson instead of creating a new one. | `src/gradata/_core.py:421-435`, `:444-469`. |
| Severity threshold | `min_severity` defaults to `as-is`, so even trivial edits are eligible unless caller raises threshold. | `src/gradata/_core.py:102`, `:356-358`; severity map in `_confidence.py:250-254`. |
| Poisoning | If >40% contradictory corrections in a category and at least 4 corrections, skip confidence updates for that category. | `src/gradata/enhancements/self_improvement/_confidence.py:166-171`, `:186-224`, `:719-721`, `:785-787`. |
| Machine mode | >25 corrections softens penalties and raises kill limits. | `_confidence.py:160-164`, `:227-247`, `:722-725`. |
| Testability by session type | Skips categories not testable in current session type. | `_confidence.py:256-295`, `:781-783`. |
| Confidence scoring | Reinforcing corrections add FSRS/Bayesian bonus and fire_count; contradictions/unknown apply capped penalty; survival bonus does not increment fire_count without injection evidence. | `_confidence.py:815-837`, `:838-893`, `:894-934`. |
| Per-session cap | Caps confidence delta to +/-0.30 and blocks multiple tier transitions in a session. | `_confidence.py:950-975`, `:992-997`; `_graduation.py:270-278`. |
| Promotion fire floors | INSTINCT->PATTERN requires confidence > threshold and min fire_count; PATTERN->RULE requires rule threshold, min fire_count, and Beta-LB gate in full graduation. | `_confidence.py:1002-1012`; `_graduation.py:137-162`, `:322-329`, `:447-459`. |
| Graduation duplicate gate | PATTERN->RULE skips candidates too similar to existing RULE descriptions. | `_graduation.py:217-232`, `:332-355`. |
| Graduation contradiction gate | PATTERN->RULE skips candidates classified as contradicting existing rules. | `_graduation.py:356-369`. |
| Graduation paraphrase robustness | PATTERN->RULE skips fragile wording when rotated-word similarity <0.25. | `_graduation.py:371-391`. |
| Rule-to-hook empirical gate | New RULE may promote to deterministic hook only if empirical gate passes. | `_graduation.py:410-444`; `rule_pipeline.py:480-499`. |

## Synthetic pass-through evidence

Command run:

```bash
PYTHONPATH=/home/olive/work/gradata-sdk/Gradata/src python3 /tmp/gra22_synthetic_audit.py
```

Output:

```text
synthetic_audit_start
corrupt_empty: rejected: ValueError: Both draft and final are empty — nothing to correct.
corrupt_identical: rejected: ValueError: draft and final are identical — no correction detected.
duplicate_e1_keys: ['lessons_created']
duplicate_e2_dedup: {}
lessons_md_lines: 6
lessons_md: [2026-06-02] [INSTINCT:0.71] PROCESS: Use 'read_file' instead of 'cat' |   Fire count: 1 | Sessions since fire: 1 | Misfires: 0 |   Corrections: 1 |   Scope: {"correction_scope": "domain"} |   Beta params: {"alpha": 2.0, "beta": 1.0} |   Metadata: {...}
low_signal_fire0: INSTINCT 0.6 0 graduated_count 0
low_signal_rule_fire1: PATTERN 0.95 1 graduated_count 0
thresholds: {'pattern': 0.6, 'rule': 0.9}
```

Interpretation:

- Corrupt/no-op corrections are rejected before storage.
- Repeating the same correction did not create a second lesson; the temp brain ended with one lesson and one correction id.
- Low-signal/no-fire candidates do not graduate: INSTINCT at 0.60/fire_count=0 stays INSTINCT, and PATTERN at 0.95/fire_count=1 stays PATTERN because the fire-count floor blocks RULE.

## Specific overlap: spine vs satellite modules

| Satellite | Overlap with graduation/self_improvement spine | Evidence | Recommendation |
|---|---|---|---|
| `rule_pipeline.py` | Re-runs canonical graduation, lifts correction patterns into lessons, writes `lessons.md`, creates skills, promotes hooks. This is partly an orchestrator, partly a second graduation/export surface. | `rule_pipeline.py:48-65` maps sessions to state/confidence; `:68-130` creates Lesson objects from patterns; `:133-214` generates SKILL.md; `:430-443` calls `_graduate`; `:470-474` writes lessons; `:480-499` promotes hooks. | Keep as orchestrator only. Move `_patterns_to_graduated_lessons` evidence mapping behind a named backfill API; move skill generation to export module; keep `_graduate` as the only state transition authority. |
| `meta_rules.py` | Has its own rule eligibility, scoring, validation, formatting, and injection eligibility separate from Lesson graduation. | `meta_rules.py:7-19` filters RULE/PATTERN and decays; `:94-98` injectable source filter; `:129-159` applicability scoring; `:542-585` contradiction validation; `:593-670` prompt formatting. | Keep as post-RULE synthesis only. Do not let meta-rules influence base Lesson state; consolidate contradiction validation terms with `_classify_correction_direction`. |
| `behavioral_engine.py` / CARL | Maintains separate directive/constraint registry and priority model, while Brain still exposes CARL constraints. | `behavioral_engine.py:20-31` priority enum; `:70-113` Directive constraints; `:116-180` registry matching; `brain.py:2146-2148` exposes `get_constraints()` as CARL. | Treat as legacy static-directive layer. Candidate for consolidation into exported RULE/AGENTS injection or generated deterministic hooks; avoid parallel prompt-injection rule store. |
| CARL filesystem/export remnants | Legacy `.carl` dirs and export paths remain outside lessons.md/RULE pipeline. | `_paths.py:41,75,136,179` defines CARL paths; `_export_brain.py:228-231` exports CARL loop/global; `_manifest_metrics.py:455-476` counts CARL rules. | Deprecate CARL filesystem in favor of `rule_export` targets. Keep read-only import for backward compatibility. |
| `scoring/*` | Analytics and threshold calibration can be mistaken for graduation scoring; some modules correctly delegate, others compute parallel metrics. | `scoring/brain_scores.py:8-14` says delegate, fallback only; `scoring/correction_tracking.py:27-62` defines correction metrics; `scoring/gate_calibration.py:54-100` separate threshold calibration. | Keep analytics read-only. Prefix/report as telemetry, not graduation gates, unless explicitly wired into `_confidence.graduation_thresholds()`. |
| `agent_graduation.py` | Separate agent-level lesson profiles use same constants and Lesson model, with approval gate graduation. | `enhancements/graduation/agent_graduation.py:6-24` explains agent graduation; `:41-55` imports spine constants; `hooks/agent_graduation.py:8-35` emits AGENT_OUTCOME. | Keep separate domain (agent profiles), but avoid duplicating state-machine thresholds; route any state transitions through self_improvement or clearly document divergence. |

## Concrete deletion/consolidation candidates (recommendations only; no deletion done)

1. Consolidate `rule_pipeline._generate_skill_file()` into `brain_export_skill()` / `rule_export.py`.
   - Evidence: `rule_pipeline.py:133-214` writes SKILL.md independently; `_core.py:1647-1815` already exports full skill directories.
2. Move `rule_pipeline._patterns_to_graduated_lessons()` into a named backfill/migration module.
   - Evidence: `rule_pipeline.py:68-130` creates lessons from `correction_patterns`, bypassing normal correction ingestion and relying on `_state_for_sessions()` evidence mapping.
3. Deprecate CARL filesystem paths as write targets.
   - Evidence: `_paths.py:41,75,136,179`, `_export_brain.py:228-231`, `_manifest_metrics.py:455-476`; static CARL lives parallel to lesson/RULE export.
4. Consolidate contradiction detection vocabulary.
   - Evidence: `_confidence.py:797-813` uses `_classify_correction_direction`; `_graduation.py:356-369` uses it for graduation; `meta_rules.py:542-585` has separate keyword-overlap+reversal logic.
5. Make AGENTS.md export part of the Stop/post-graduation flow or explicitly remove it from that promise.
   - Evidence: implementation exists in `rule_export.py:147-167`; Stop waterfall lacks export call at `session_close.py:317-340`.

## Top 3 noise classes that escape current filtering

1. Trivial/as-is edits can become lessons by default.
   - Evidence: `brain_correct(... min_severity="as-is")` at `_core.py:102`; extraction proceeds when severity rank >= min severity at `_core.py:356-358`. A typo-level correction is therefore eligible unless caller opts into a higher threshold.
   - Impact: typo/style micro-edits can seed INSTINCT lessons and later clutter prompts.
   - Follow-up: default hook path should likely use `min_severity="minor"` or require behavioral extractor confidence before lesson creation.

2. Semantic duplicates with different draft/final text can evade observation dedup and duplicate PATTERNs can coexist until RULE-time dedup.
   - Evidence: observation dedup fingerprints exact `(draft[:500], final[:500], category)` only at `dedup.py:247-263`; graduation duplicate gate compares PATTERN candidates only against existing RULEs at `_graduation.py:217-232` and `:332-355`.
   - Impact: repeated paraphrased corrections can create/reinforce sibling PATTERNs; only the final RULE promotion is protected against existing RULE duplicates.
   - Follow-up: add semantic duplicate check among active INSTINCT/PATTERN lessons before creating a new lesson, using existing `best_similarity` path and stricter per-category thresholds.

3. Ambiguous/UNKNOWN direction corrections are treated as penalties, not quarantined.
   - Evidence: `_confidence.py:797-813` leaves direction as `UNKNOWN` when no explicit direction/classifier match is found; `_confidence.py:837-893` sends `CONTRADICTING or UNKNOWN` through the penalty path.
   - Impact: vague corrections in the same category can decay unrelated lessons instead of being ignored or approval-gated.
   - Follow-up: require explicit `CONTRADICTING` or sufficiently high similarity overlap before applying contradiction penalty; otherwise create a pending review candidate or no-op.

## Verification / commands run

- Confirmed assigned issue via Paperclip curl and marked `GRA-22` in_progress.
- Inspected code read-only under `/home/olive/work/gradata-sdk/Gradata`.
- Ran synthetic script under `/tmp/gra22_synthetic_audit.py`; no repo files changed.
- No git commit/PR: issue is explicitly read-only and asks for a Paperclip audit document.

## Model/CLI usage transparency

- Main operator: Hermes CLI session.
- Attempted `delegate_task` for three subagents; it failed because provider `cli-shim` had no API key/auth in this session.
- Used local tool execution and explicit `[ollama/qwen3:32b]` routed mechanical/source-inspection steps. No paid API calls were used.


## 2026-06-03 heartbeat verification addendum

Current checkout verified: `/home/olive/work/gradata/Gradata` (`origin=https://github.com/Gradata/gradata.git`, branch `gra-1163-post-session-hooks`). The repo was already dirty with unrelated untracked files (`examples/langchain_agent.py`, `tests/test_claude_code_runtime.py`); this audit remained read-only and did not modify repo files.

Additional synthetic pass-through evidence run on 2026-06-03:

```text
duplicate_state= PATTERN
low_signal_state= PATTERN fire_count= 1
lifted= [('CODE', 'never fabricate test output', 'PATTERN', 2)]
corrupt_parse_count= 0
```

Interpretation: duplicate PATTERN similar to an existing RULE was blocked from RULE promotion; high-confidence low-fire PATTERN stayed PATTERN; `[AUTO]` correction_patterns rows were dropped while a 2-session real correction lifted only to PATTERN; corrupt non-lesson markdown parsed to zero lessons.

Key current-checkout citations confirmed:

- Hook capture: `src/gradata/hooks/auto_correct.py:39-44`, `:66-96`, `:99-138`.
- Daemon `/correct`: `src/gradata/daemon.py:412-441`.
- Brain entrypoint: `src/gradata/brain.py:479-560`.
- Stop waterfall: `src/gradata/hooks/session_close.py:46-54`, `:97-110`, `:148-170`, `:317-340`.
- Graduation gates: `src/gradata/enhancements/self_improvement/_graduation.py:137-162`, `:322-355`, `:356-391`, `:447-459`.
- Pattern bridge / pipeline: `src/gradata/enhancements/rule_pipeline.py:68-130`, `:415-443`, `:470-499`.
- AGENTS export implementation: `src/gradata/enhancements/rule_export.py:1-7`, `:24-58`, `:70-93`, `:147-167`; CLI write path at `src/gradata/cli.py:315-347`.

Conclusion unchanged: the audit acceptance criteria are satisfied as a Paperclip `audit-report` document; no code change/PR is appropriate for this read-only issue. Follow-up implementation issues should target AGENTS export wiring, active-pattern semantic dedup, and default trivial/noise filtering.

---

Source: Paperclip GRA-22 `audit-report`, document id 6902527f-9c9f-4812-8518-89ae1a313f16, revision 2.
