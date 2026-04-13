-- Gradata Cloud: Anonymous SDK activation telemetry (opt-in only).
-- Run this in Supabase SQL Editor (Dashboard -> SQL -> New Query)
--
-- What lives here: event name, sha256(machine_id), UTC timestamp, sdk version,
-- the backend's received_at timestamp, and the source IP (truncated to /24 for
-- v4 or /48 for v6 upstream — we record the raw IP here only for the rate
-- limiter; it is NOT exposed in any read path).
--
-- What does NOT live here: user email, user ID, workspace ID, lesson text,
-- correction content, draft/final previews, file paths. The SDK strips all
-- of that before sending.

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
