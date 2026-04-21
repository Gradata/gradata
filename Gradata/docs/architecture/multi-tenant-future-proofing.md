# Multi-Tenant Future-Proofing Plan (Gradata SDK + Cloud)

**Written:** 2026-04-17 pre-user-2
**Goal:** Make the irreversible decisions NOW so user #2 doesn't force a rewrite.
**Non-goal:** Premature cloud migration. Local-first stays the moat.

---

## Ground Truth (Today)

- 40+ SQLite tables in `brain/system.db`, 21,206 events in `events.jsonl`
- **No `tenant_id` anywhere.** Single-tenant assumption baked into schema.
- Embeddings stored as BLOB (`brain_embeddings`); FTS5 via `brain_fts`.
- `events.scope` column exists (default 'local') — partial seed for tenant scoping, not used.
- `sync_state` table exists per source but not cloud-bound.
- Proprietary dashboard / team-sharing code in `gradata_cloud_backup/`. Graduation runs locally in the OSS SDK.
- Open SDK is Apache-2.0 — cannot require cloud to run.

## Architectural Decisions (Lock In Now)

### 1. Local-first stays the source of truth
SDK writes to local SQLite + jsonl and runs the full learning loop (graduation, synthesis, rule-to-hook promotion) locally. Cloud is a **sync target + dashboard + future team + future shared-corpus surface** — not a gate on the local loop. Do NOT migrate SDK storage to Postgres. Reasons: privacy, offline, open source, speed.

### 2. Supabase is the cloud target
Postgres + Auth + RLS + pgvector + Realtime in one project. Free tier covers pre-revenue. Alternative (Neon + Clerk + own RLS) costs weeks you don't have.

### 3. Tenant key model
- `tenant_id UUID` on every per-tenant row (nullable only during migration)
- `tenant_id IS NULL` = global / shareable (meta-rules marked `visibility='global'`)
- Tenant UUID generated locally on SDK install, registered with cloud on first sync

### 4. Rule visibility levels
Add `visibility TEXT` to `meta_rules`, `rules` (if separate table emerges):
- `private` — stays local forever (default)
- `shared` — opt-in to cross-tenant mining (anonymized)
- `global` — Gradata-curated, pushed to all tenants (e.g., quality_gates, truth_protocol)

### 5. Proprietary boundary
- **Open SDK** writes raw events, computes local diffs, injects rules, graduates lessons, and synthesizes meta-rules locally (BYO API key or Claude Code Max OAuth).
- **Cloud (proprietary)** owns: dashboard/visualization, cross-tenant meta-rule corpus (opt-in donation), team sharing, billing, licensing.
- Clean interface: SDK pushes events + graduated rules to cloud. Cloud reflects them back through UI. Cloud never re-runs graduation.

### 6. Schema versioning
Add `schema_version INT` to event envelope + a `migrations` table. Forward-only migrations. SDK refuses to run against incompatible brain.

---

## Per-Table Tenant Classification

These lists are the authoritative contract for migration 001
(`src/gradata/_migrations/001_add_tenant_id.py` — `PER_TENANT_TABLES` and
`MIXED_VISIBILITY_TABLES`). Keep them in sync with that file.

**Per-tenant (add `tenant_id` NOT NULL, backfill to the primary tenant UUID):**
deals, signals, activity_log, facts, decisions, pipeline_snapshots, daily_metrics, prep_outcomes, session_metrics, session_gates, events, output_classifications, correction_severity, tasks, agent_jobs, enrichment_queue, enrichment_processed_files, demo_recordings, pending_approvals, brain_embeddings, brain_fts_content, audit_scores, gate_triggers, lesson_applications, rule_provenance, correction_patterns, entities, relationships, ablation_log, rule_canary, lesson_transitions, sync_state

**Mixed (add `tenant_id` nullable + `visibility`):**
meta_rules, frameworks, rule_relationships

**Global only (no `tenant_id`):**
periodic_audits (template), sqlite_sequence

---

## Execution Plan

### Phase 0 — Schema migration (4-6 hours, BEFORE user 2)

Files to create:

1. `src/gradata/_migrations/001_add_tenant_id.py`
   - Add `tenant_id TEXT DEFAULT '<oliver-uuid>'` to all per-tenant tables
   - Add `visibility TEXT DEFAULT 'private'` to meta_rules, frameworks, rule_relationships
   - Add `schema_version INT DEFAULT 1` to events
   - Backfill existing 21k events with Oliver's tenant UUID
   - Creates `migrations` table, inserts migration record
   - **Idempotent** — check `migrations` table before running

2. `src/gradata/_migrations/tenant_uuid.py`
   - Generates UUID once, stores in `brain/.tenant_id`
   - Registers with cloud on first sync

3. `src/gradata/_tenant.py`
   - `get_tenant_id()` reads from `brain/.tenant_id`, generates if missing
   - All new `events`/`facts`/`decisions` writes include `tenant_id`
   - Audit: find all `INSERT INTO` sites in SDK, gate through tenant-aware writer

### Phase 1 — Cloud target (1 day)

4. Supabase project `gradata-cloud-prod`
5. `src/gradata/_migrations/cloud_schema.sql` — mirrors local per-tenant schema with RLS
   - Enable pgvector, create embedding columns as `vector(1536)`
   - RLS policy: `tenant_id = auth.uid()::text` on every per-tenant table
   - Global tables readable by all authenticated users
6. `src/gradata/_migrations/cloud_sync.py`
   - Push deltas since `sync_state.last_sync_ts`
   - Pull: global + shared meta-rules matching this tenant's scopes
   - Respects `visibility` — never pushes `private` rows
   - Idempotent via (tenant_id, source_id) upsert
   - Offline-tolerant — queues locally if cloud unreachable

### Phase 2 — Identity & onboarding (1 day)

7. `src/gradata/_migrations/onboard_tenant.py`
   - Takes email + Supabase auth token
   - Creates local `brain/` directory with schema
   - Registers tenant UUID in cloud
   - Pulls global meta-rules as seed
   - Seeds `credit_budgets` defaults
8. Per-tenant secret vault
   - Each user supplies own Anthropic/Apollo/Gmail keys
   - Stored in `~/.gradata/secrets/<tenant_id>.enc` (local, encrypted)
   - Cloud never sees raw keys
9. `docs/cloud-contract.md` — versioned API between SDK and cloud. Breaking changes require version bump.

### Phase 3 — Verification (half day)

10. Spin up a **test tenant** (not Oliver, not user #2). Run full flow:
    - Onboard → writes local brain → corrects a draft → rule graduates **locally** → syncs reflection up to cloud → dashboard renders.
    - Verify RLS: test tenant cannot see Oliver's events (SQL probe)
    - Ablation: disable cloud sync → SDK still works fully offline, including graduation + synthesis.

### Phase 4 — Explicitly deferred

- Cross-tenant meta-rule mining (needs N≥5 brains for signal)
- Billing integration (manual invoice until revenue)
- Graduation engine as standalone cloud service (current local inference fine)
- pgvector semantic search replacing local FTS5 (premature)
- Frontend / admin UI (Supabase dashboard suffices)
- Schema rewrite to Postgres locally (local SQLite is a feature)

---

## Risks & Mentor Notes

1. **The ONE irreversible decision is tenant_id.** Everything else can be added later. If you skip this before user 2, you're signing up for a painful data migration with two users' rows interleaved.

2. **RLS mistakes leak data across tenants.** Write RLS policy tests (`src/gradata/_migrations/test_rls.py`) that attempt cross-tenant reads and assert failure. Run in CI.

3. **Sync direction conflicts.** If Oliver's SDK and user 2's SDK both edit the same global meta-rule locally, last-write-wins will drop data. Solution: global rules are read-only locally; edits go through cloud PR-style flow. Defer until it matters.

4. **Open source tension.** The SDK is Apache-2.0 but `src/gradata/_migrations/cloud_sync.py` calls proprietary cloud. Keep cloud_sync in a separate package (`gradata-cloud-client`) that's MIT or closed, SDK imports optionally. Don't pollute Apache license clean-room.

5. **"Future proof now" is a trap.** Most future-proofing is over-engineering. This plan is narrow by design: tenant_id, RLS, visibility, schema version. That's it. Everything else waits for real signal from user 2.

6. **User 2 will break assumptions.** Their brain will have different prospect names, different ICP, different voice. Budget 1-2 days after onboarding for "weird first multi-tenant bug" fixes.

---

## Success Criteria (Before User 2 Onboards)

- [ ] `tenant_id` column on all per-tenant tables
- [ ] Oliver's existing 21k events backfilled with his UUID
- [ ] `visibility` column on meta_rules with private default
- [ ] Supabase project live with RLS policies
- [ ] `cloud_sync.py` pushing + pulling successfully (Oliver only)
- [ ] Test tenant can onboard via script, cannot see Oliver's data
- [ ] SDK works fully offline (cloud sync optional)
- [ ] `docs/cloud-contract.md` versioned and checked in

Total estimate: **2-3 days focused work**. Not a rewrite.
