-- Gradata Cloud: Soft delete + GDPR support
-- Run this in Supabase SQL Editor after 004.
--
-- Adds `deleted_at TIMESTAMPTZ` to users/workspaces/brains so /me/delete can
-- tombstone a user without losing the data immediately. A nightly Railway
-- cron (separate PR) will purge rows where `deleted_at < now() - 30 days`.
--
-- Existing RLS policies SHOULD filter deleted_at IS NULL; this migration
-- adds a convenience view but does NOT rewrite policies. App-side queries
-- must filter on their own (enforced in app/db + route handlers).

-- ============================================================
-- COLUMNS
-- ============================================================

-- users (auth.users is managed by Supabase; we store our own shadow row in
-- public.users when/if we need to attach product-level tombstones). For now
-- we add deleted_at to the tables we actually own.

ALTER TABLE workspaces
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

ALTER TABLE brains
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

-- public.users: a shadow table for product-level user metadata + tombstones.
-- Keeps auth.users untouched (Supabase-managed) while giving us somewhere to
-- record deletion intent and the 30-day purge deadline.
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT,
    deleted_at TIMESTAMPTZ,
    purge_after TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_workspaces_deleted_at ON workspaces(deleted_at)
    WHERE deleted_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_brains_deleted_at ON brains(deleted_at)
    WHERE deleted_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_deleted_at ON users(deleted_at)
    WHERE deleted_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_purge_after ON users(purge_after)
    WHERE deleted_at IS NOT NULL;

-- ============================================================
-- RATE LIMIT LEDGER for /me/export (1 call per 24h per user)
-- ============================================================

CREATE TABLE IF NOT EXISTS gdpr_export_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_gdpr_export_requests_user_created
    ON gdpr_export_requests(user_id, created_at DESC);

ALTER TABLE gdpr_export_requests ENABLE ROW LEVEL SECURITY;

-- Postgres does not support `CREATE POLICY IF NOT EXISTS`; drop-then-create
-- keeps the migration idempotent across re-runs (local dev / SQL Editor).
DROP POLICY IF EXISTS gdpr_export_self ON gdpr_export_requests;
CREATE POLICY gdpr_export_self ON gdpr_export_requests
    FOR ALL USING (user_id = auth.uid());

-- ============================================================
-- NOTE: actual purge runs out-of-band (TODO: Railway cron).
--   DELETE FROM users WHERE deleted_at IS NOT NULL AND purge_after < now();
-- ============================================================
