# SDK Graduation Forensics — oliver-admin brain (3b49e9c6)

## Headline finding

The "missing lessons in 25+ categories" symptom is most likely a **bypass-path issue**, not a category-filter bug.

**Top suspects:**
1. (d) `record_correction()` and connected-cloud mode bypass local lesson creation entirely
2. (b) Graduation thresholds too strict for low-volume categories (need confidence>0.60 + 3 fires for PATTERN, then 0.90 + 5 fires + Beta-LB ≥0.85 for RULE)
3. (c) Cloud materializer only consumes `RULE_*` events, NOT `LESSON_CHANGE created` — so even if SDK creates a lesson locally, it may never land in cloud's `lessons` table

## 1. Call path (correction → lesson)

| Step | File:line                                        | Notes |
|------|--------------------------------------------------|-------|
| 1    | `brain.py:400, 432-449` `Brain.correct()`        | Public entry; invalidates rule cache |
| 2    | `_core.py:138-146` cloud bypass                  | If `_cloud.connected` and `auto_heal=False` → returns `_cloud.correct(...)` immediately. Skips local diff/classify/lesson write entirely. |
| 3    | `_core.py:151-190` local diff/classify           | Defaults correction category to first classification result |
| 4    | `_core.py:268-308` `CORRECTION` event emit       | Persisted via JSONL + SQLite `events` table (NOT a local `lessons` table) |
| 5    | `_core.py:343-518` lesson create/reinforce       | Reinforces best same-category similar lesson OR appends new `Lesson(INSTINCT, conf=0.60)`. New = `LESSON_CHANGE created`. Reinforce = `LESSON_CHANGE reinforced`. |
| 6    | `_core.py:608-622` `update_confidence()`         | Inline-promotes states only if fire-count gates met |
| 7    | `_core.py:820-865, 931-967` `brain.end_session()`| Calls `update_confidence()` AND canonical `graduate()`, logs `lesson_transitions` |
| 8    | `hooks/session_close.py:97-110` hook path        | Also runs `graduate()` BUT writes only `active` lessons back. Discards `graduated` list. **Dangerous.** |
| 9    | `_migrations/__init__.py:33-75` SDK schema       | Creates `events`, `lesson_transitions`, `pending_approvals`, `rule_provenance`. **No canonical local `lessons` table.** |

## 2. Filtering / dropping points

- **`record_correction()`** — emits CORRECTION only, never runs diff/classification/lesson creation. `brain.py:467-501`
- **Cloud bypass** — `_core.py:138-146` short-circuits before local lessons exist; depends on cloud server-side graduation
- **Observation dedup** — near-duplicate corrections suppress new lesson creation. `_core.py:329-356`
- **Severity gate** — `_SEV_RANK[diff.severity] >= _SEV_RANK[min_severity]`. Default permissive. `_core.py:31-32, 356-358`
- **Similarity dedup is category-local** — only existing lessons with same category are similarity candidates. High similarity → reinforce existing. Explains low `created` count vs high `LESSON_CHANGE` count. `_core.py:421-450`
- **Approval gating** — untrusted/adversarial corrections force `approval_required=True`, conf=0.0, `pending_approval=True`, `graduate()` skips. `_core.py:213-252, 506-518`; `_graduation.py:244-245`
- **`scope='one_off'` lessons** never promote past INSTINCT. `_graduation.py:247-259`
- **Session-type gating** in `update_confidence()` — only updates testable categories for `systems` or `sales` session types. Unknown/`full` allows all. `_confidence.py:244-284, 768-770`
- **Poisoning defense** — skips confidence updates for categories with ≥40% contradictory corrections + ≥4 corrections. `_confidence.py:166-172, 707-774`
- **Canonical `graduate()` silent blocks** — duplicate RULE similarity >0.85, contradiction, fragile wording <0.25, pending approval, one-off scope, per-session tier cap. `_graduation.py:314-386`
- **`hooks/session_close._run_graduation()`** — discards `graduated` list, writes only `active`. RULE can disappear from `lessons.md`. `hooks/session_close.py:108-109`
- **Meta-rules require ≥3 eligible PATTERN/RULE lessons** in a group. `meta_rules.py:235-256, 366-399`
- **LearningPipeline discriminator** can say "discard" but is telemetry-only — does not block. `_core.py:728-749`

## 3. Threshold values

| Threshold                          | Value                                | File:line |
|------------------------------------|--------------------------------------|-----------|
| Initial lesson confidence          | 0.60                                 | `_confidence.py:46` |
| INSTINCT → PATTERN                 | conf > 0.60 AND fire_count >= 3      | `_confidence.py:47, 55, 995-999`; `_graduation.py:439-451` |
| PATTERN → RULE                     | conf >= 0.90 AND fire_count >= 5     | `_confidence.py:54-56, 989-994`; `_graduation.py:314-321` |
| Beta lower-bound gate (canonical)  | enabled, threshold 0.85, min fires 5 | `_graduation.py:101-155` |
| Per-session conf delta cap         | 0.30                                 | `_confidence.py:153-158, 937-961` |
| Duplicate graduation block         | similarity > 0.85 vs existing RULE   | `_confidence.py:138-140`; `_graduation.py:324-344` |
| Fragile wording block              | self-paraphrase similarity < 0.25    | `_graduation.py:363-386` |
| Kill/idle (human)                  | INFANT 8, ADOLESCENT 12, MATURE 15, STABLE 20 | `_confidence.py:88-94` |
| Kill/idle (machine)                | 16/20/24/30                          | `_confidence.py:124-129` |
| Machine context auto-detect        | corrections > 25 (or >30 in end_session) | `_confidence.py:160-164, 215-235`; `_core.py:859-863` |
| Meta-rule synthesis                | min group size 3, RULE conf floor 0.90, decay 0.05/session after 20 sessions, drop <0.10 | `meta_rules.py:256-259, 348-399` |

## 4. Category taxonomy

**There is no canonical category enum.** `Lesson.category` is a free string (`_types.py:158-166`). `Brain.correct(category=...)` accepts free text, uppercases, persists.

Multiple overlapping/partial taxonomies:

| Source | Categories |
|--------|------------|
| `edit_classifier`                | FACTUAL, STYLE, STRUCTURE, TONE, PROCESS, CONTENT |
| `_tag_taxonomy` defaults         | CONTENT, FACTUAL, TONE, STRUCTURE, STYLE, DRAFTING, ACCURACY, PROCESS, ARCHITECTURE, COMMUNICATION, CONTEXT, CONSTRAINT, DATA_INTEGRITY, THOROUGHNESS, COST, VOICE, QUALITY, CRM, STRATEGY, ENTITIES, POSITIONING, PRESENTATION, STARTUP |
| `CATEGORY_SESSION_MAP` systems   | ARCHITECTURE, PROCESS, TOOL, THOROUGHNESS, CONTEXT |
| `CATEGORY_SESSION_MAP` sales     | DRAFTING, LEADS, PRICING, DEMO_PREP, POSITIONING, COMMUNICATION, TONE, ACCURACY, DATA_INTEGRITY |
| Meta-rule task mapping           | PROCESS, TOOL, THOROUGHNESS, CONTEXT, PRICING, ACCURACY, CODE, CONTENT, etc. |
| Memory projection                | own map, unknown → `decisions.md` |
| Structured correction types      | factual_error, style, tone, approach, omission, hallucination, format, scope, unknown — stored under `data.structured`, NOT the lesson category |

**Fragmentation risks:**
- `FACT` (in your prod data) vs `FACTUAL` (in classifier/taxonomy)
- `FORMAT` not in any taxonomy default
- `CONFIG` not in any taxonomy default
- `GOAL` not in any taxonomy default
- `PRICING`, `TOOL`, `FORMAT`, `CONFIG`, `FACT`, `GOAL` absent from `_tag_taxonomy` defaults

Free-text categories are accepted but unknown ones may be excluded from session-type updates, meta-rule task mapping, projection buckets, or analytics grouping.

## 5. Hypothesis ranking

| Rank | Hypothesis | Likelihood | Reasoning |
|------|-----------|------------|-----------|
| 1 | (d) Bypass path | HIGHEST | `record_correction()` emits CORRECTION only; cloud-connected returns before local lesson. Fits "corrections present, zero LESSON_CHANGE created or active lesson lineage". |
| 2 | (b) Thresholds too strict | HIGH | New=0.60 conf, 0 fires; need >0.60+3 fires for PATTERN, then 0.90+5 fires + Beta-LB≥0.85 for RULE. Reinforce path can penalize rather than reinforce when descriptions don't overlap (`_confidence.py:784-879`). |
| 3 | (c) Projector/materializer gap | LIKELY | Public SDK has no local `lessons` table. Cloud materializer only consumes `RULE_*` events, NOT `LESSON_CHANGE created` (`cloud/materializer.py:43-55`). |
| 4 | (e) Free-text fragmentation | MEDIUM | Not hard-dropped, but multiple partial allowlists mean unknown categories can be omitted from session-type updates, meta-rule task mapping, projection buckets. `FACT` vs `FACTUAL` concrete risk. |
| 5 | (a) Category hard gating | LOWER | Allowlists exist for session-type testability, projection, meta-rule mapping, but the primary local correction-to-lesson path does not reject by enum. |

## 6. Recommended next experiments

### Experiment 1: SQL path split (run on prod Supabase)

```sql
WITH corr AS (
  SELECT event_id, type, data->>'category' AS category,
         data->>'platform_source' AS platform_source
  FROM events
  WHERE brain_id = '3b49e9c6-2cf1-4e6f-b9bf-51a618fe830a'
    AND type='CORRECTION'
), created AS (
  SELECT data->>'source_correction_id' AS correction_id,
         data->>'lesson_category' AS lesson_category
  FROM events
  WHERE brain_id = '3b49e9c6-2cf1-4e6f-b9bf-51a618fe830a'
    AND type='LESSON_CHANGE'
    AND data->>'action'='created'
)
SELECT corr.platform_source, corr.category,
       COUNT(*) AS corrections,
       COUNT(created.correction_id) AS created_lessons
FROM corr LEFT JOIN created ON corr.event_id::text = created.correction_id
GROUP BY 1,2 ORDER BY corrections DESC;
```

This reveals whether the missing categories arrived via `record_correction()` (which won't have matching `LESSON_CHANGE created`) vs `Brain.correct()` (which would).

### Experiment 2: Bypass volume audit

Count CORRECTION rows where `source != 'brain.correct'` or where data lacks `draft_text/final_text` — likely `record_correction()` or hook-only captures.

### Experiment 3: State + fires audit

Group active `lessons` by category + state + confidence + fire_count + pending_approval + correction_scope. Look for categories stuck at INSTINCT with fire_count<3, or pending_approval=1, or scope='one_off'.

### Experiment 4: Reproduction test

Call `Brain.correct(..., category='PROCESS')` 3-6 times with semantically similar corrections, then `brain.end_session()`. Assert lesson created, fire_count incremented, PATTERN/RULE transition. Repeat using `record_correction()` to prove bypass.

### Experiment 5: Taxonomy normalization

Map likely aliases:
- `FACT` → `FACTUAL`
- `FORMAT` → `STYLE` or `STRUCTURE`
- `CONFIG` → `TOOL` or `PROCESS`
- `GOAL` → `STRATEGY`

Test whether normalizing before `Brain.correct()` collapses missing zero-lesson buckets into existing lesson categories.

## 5-line summary (from worker)

1. Highest-likelihood gap: corrections may enter via `record_correction()` or connected cloud mode, both bypass local lesson creation/graduation.
2. Local `Brain.correct()` writes lessons to `lessons.md`; the public SDK does not maintain a canonical local `lessons` table.
3. Graduation thresholds are strict: INSTINCT→PATTERN needs `conf > 0.60` and `fire_count >= 3`; PATTERN→RULE needs `conf >= 0.90`, `fire_count >= 5`, plus Beta-LB `>= 0.85`.
4. Categories are free text in lessons; taxonomy validation only debug-logs, so unknown categories are not hard-dropped, but fragmentation like `FACT` vs `FACTUAL` is likely.
5. Dangerous redundancy: `hooks/session_close._run_graduation()` writes only active lessons after `graduate()`, while cloud materializer only consumes `RULE_*` events, not `LESSON_CHANGE created`.
