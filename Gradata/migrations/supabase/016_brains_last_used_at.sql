-- Migration 016: Add last_used_at column to brains table
-- Used by auth.py verify_api_key to stamp the column on each key use;
-- returned by the brains list endpoint.
-- Run in Supabase SQL editor.

ALTER TABLE brains
  ADD COLUMN IF NOT EXISTS last_used_at TIMESTAMPTZ;
