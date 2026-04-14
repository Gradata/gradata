-- Gradata Cloud: Anonymous SDK activation telemetry (opt-in only).
-- Run this in Supabase SQL Editor (Dashboard -> SQL -> New Query)
--
-- What lives here: event name, sha256(machine_id), UTC timestamp, sdk version,
-- and the backend's received_at timestamp.
--
-- What does NOT live here: user email, user ID, workspace ID, lesson text,
-- correction content, draft/final previews, file paths, or source IP. The
-- SDK strips payload PII before sending; the backend does not persist the
-- client IP (it is used only for the in-memory rate limiter and dropped
-- once the sliding window expires). The ``source_ip`` column is retained
-- as nullable for backward compatibility and is always NULL going forward.

CREATE TABLE IF NOT EXISTS telemetry_events (
    id BIGSERIAL PRIMARY KEY,
    event TEXT NOT NULL CHECK (length(event) <= 64),
    user_id TEXT NOT NULL CHECK (length(user_id) = 64),      -- sha256 hex
    sdk_version TEXT NOT NULL CHECK (length(sdk_version) <= 32),
    event_ts TIMESTAMPTZ NOT NULL,                            -- client-sent
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),           -- server-side
    source_ip INET                                            -- rate limiter only
);

-- Activation funnel queries need to group by event over a time window.
CREATE INDEX IF NOT EXISTS idx_telemetry_events_event_ts
    ON telemetry_events (event, received_at DESC);

-- Dedupe / conversion queries need the user_id.
CREATE INDEX IF NOT EXISTS idx_telemetry_events_user_id
    ON telemetry_events (user_id);

-- RLS: This table is written by the service role only (no auth header on
-- the /telemetry/event endpoint). Block all anon/authenticated reads so a
-- leaked anon key can't enumerate the install base.
ALTER TABLE telemetry_events ENABLE ROW LEVEL SECURITY;

-- Explicit deny-all policy. PostgreSQL's "no policy = deny" default is
-- robust, but an explicit policy makes the intent visible to anyone reading
-- the schema and survives later additions of permissive policies for other
-- roles. Service role bypasses RLS, which is what the backend uses.
DROP POLICY IF EXISTS telemetry_events_deny_all ON telemetry_events;
CREATE POLICY telemetry_events_deny_all
    ON telemetry_events
    FOR ALL
    USING (false)
    WITH CHECK (false);
