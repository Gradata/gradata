-- Migration 015: Deduplicate events + add UNIQUE constraint
-- id is UUID, so we use ctid (not MIN(id)) to pick one row per duplicate group.
-- Applied to prod 2026-04-24 via Management API (constraint only; 0 duplicates found).
-- Run in Supabase SQL editor.

BEGIN;

DELETE FROM events a
USING events b
WHERE a.brain_id = b.brain_id
  AND a.type = b.type
  AND a.created_at = b.created_at
  AND a.ctid > b.ctid;

ALTER TABLE events
  ADD CONSTRAINT events_brain_type_created_at_unique
  UNIQUE (brain_id, type, created_at);

COMMIT;
