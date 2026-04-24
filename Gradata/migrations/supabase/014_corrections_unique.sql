-- Migration 014: Deduplicate corrections + add UNIQUE constraint
-- id is UUID, so we use ctid (not MIN(id)) to pick one row per duplicate group.
-- Applied to prod 2026-04-24 via Management API (constraint only; 0 duplicates found).
-- Run in Supabase SQL editor.

BEGIN;

DELETE FROM corrections a
USING corrections b
WHERE a.brain_id = b.brain_id
  AND a.session = b.session
  AND a.description = b.description
  AND a.ctid > b.ctid;

ALTER TABLE corrections
  ADD CONSTRAINT corrections_brain_session_description_unique
  UNIQUE (brain_id, session, description);

COMMIT;
