-- Migration 005: UNIQUE constraint on lessons(brain_id, description)
--
-- The /sync endpoint calls db.upsert("lessons", ...) which uses PostgREST's
-- resolution=merge-duplicates. Without a UNIQUE constraint the ON CONFLICT
-- target doesn't exist, so every sync inserts duplicate rows instead of
-- merging them. This migration adds the missing constraint so upserts behave
-- idempotently per (brain_id, description).
--
-- Safety: collapse any existing duplicates before adding the constraint.
-- For each (brain_id, description) group we keep the most recently updated
-- row (fall back to highest confidence, then newest id) and delete the rest.
-- This is conservative — no lesson metadata is lost for brains that never
-- synced the same description twice.

BEGIN;

WITH ranked AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY brain_id, description
            ORDER BY updated_at DESC NULLS LAST, confidence DESC, id DESC
        ) AS rn
    FROM lessons
)
DELETE FROM lessons
WHERE id IN (SELECT id FROM ranked WHERE rn > 1);

ALTER TABLE lessons
ADD CONSTRAINT lessons_brain_id_description_key
UNIQUE (brain_id, description);

COMMIT;
