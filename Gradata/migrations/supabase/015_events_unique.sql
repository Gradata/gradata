-- Migration 015: Deduplicate events + add UNIQUE constraint
-- id is UUID, so we use ctid (not MIN(id)) to pick one row per duplicate group.
-- Applied to prod 2026-04-24 via Management API (0 duplicates found).
--
-- Idempotency: guards against pre-existing UNIQUE constraints on the same
-- columns (prod already had `events_brain_type_created_at_key` from the
-- initial table's inline UNIQUE(...) clause — this migration is a no-op there,
-- kept for fresh-DB parity).
--
-- Run in Supabase SQL editor or via Management API.

BEGIN;

DELETE FROM events a
USING events b
WHERE a.brain_id = b.brain_id
  AND a.type = b.type
  AND a.created_at = b.created_at
  AND a.ctid > b.ctid;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    WHERE t.relname = 'events'
      AND c.contype = 'u'
      -- Exact-match check (not superset): sort both sides then compare arrays.
      AND (
        SELECT array_agg(k ORDER BY k) FROM unnest(c.conkey) AS k
      ) = (
        SELECT array_agg(attnum ORDER BY attnum)::int2[]
        FROM pg_attribute
        WHERE attrelid = t.oid
          AND attname IN ('brain_id', 'type', 'created_at')
      )
  ) THEN
    ALTER TABLE events
      ADD CONSTRAINT events_brain_type_created_at_unique
      UNIQUE (brain_id, type, created_at);
  END IF;
END $$;

COMMIT;
