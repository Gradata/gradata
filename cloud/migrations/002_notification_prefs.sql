-- 002_notification_prefs.sql
-- Adds notification_prefs JSONB column to workspace_members so users can
-- persist alert toggles and digest cadence from the dashboard.

ALTER TABLE workspace_members
  ADD COLUMN IF NOT EXISTS notification_prefs JSONB NOT NULL DEFAULT '{}'::jsonb;

-- Index on the cadence key — used by the future digest scheduler to fetch
-- "all users with digest_cadence = 'weekly'" without a full table scan.
CREATE INDEX IF NOT EXISTS idx_workspace_members_digest_cadence
  ON workspace_members ((notification_prefs->>'digest_cadence'));

COMMENT ON COLUMN workspace_members.notification_prefs IS
  'Notification preferences shape: { alert_correction_spike, alert_rule_regression, alert_meta_rule_emerged, digest_cadence, digest_email, slack_webhook }';
