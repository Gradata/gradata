# Supabase schema migrations

Raw SQL migrations for the proprietary cloud Postgres (project `miqwilxheuxwafvmoajs`).
Separate from `src/gradata/_migrations/` which owns the **local SQLite** schema.

## Apply

Via Supabase Management API (token in `.env` as `SUPABASE_ACCESS_TOKEN`):

```bash
curl -sS -X POST "https://api.supabase.com/v1/projects/miqwilxheuxwafvmoajs/database/query" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -H "User-Agent: curl/8.0.1" \
  -d "$(jq -Rs '{query: .}' < migrations/supabase/014_corrections_unique.sql)"
```

The `User-Agent: curl/8.0.1` header is required to bypass Cloudflare WAF rule 1010.

Or paste into the Supabase SQL editor.

## Applied to prod

| File | Applied | Notes |
|------|---------|-------|
| 014_corrections_unique.sql | 2026-04-24 | 0 duplicates found. Prod already had `corrections_brain_session_desc_key` (inline UNIQUE from CREATE TABLE) — migration added a redundant `_unique` constraint on same columns. Both enforce; harmless. Migration now guards with a `pg_constraint` lookup so re-runs are no-ops. |
| 015_events_unique.sql      | 2026-04-24 | Same pattern: prod already had `events_brain_type_created_at_key`. Migration guards with `pg_constraint` lookup. |
| 016_brains_last_used_at.sql| 2026-04-24 | Column already existed; idempotent `IF NOT EXISTS` |

### Prod constraint state (verified 2026-04-24)

```
corrections_brain_session_desc_key              UNIQUE (brain_id, session, description)  -- pre-existing
corrections_brain_session_description_unique    UNIQUE (brain_id, session, description)  -- from 014
events_brain_type_created_at_key                UNIQUE (brain_id, type, created_at)      -- pre-existing
events_brain_type_created_at_unique             UNIQUE (brain_id, type, created_at)      -- from 015
```

Redundant pairs are functionally harmless (same column set, same enforcement). Dropping the `_key` variants is a future cleanup migration — not urgent.

## Convention

- Numbered in application order, zero-padded (`NNN_description.sql`).
- Wrap DDL + DML in `BEGIN; ... COMMIT;` so a failure rolls back.
- Deduplication on UUID-keyed tables must use `ctid`, not `MIN(id)` — Postgres has no `min(uuid)` aggregate.
- Use `IF NOT EXISTS` / `IF EXISTS` so re-runs are no-ops.
- Header comment: what it does, when applied, anything non-obvious.
