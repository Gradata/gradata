-- Gradata Cloud: Workspace invites
-- Adds pending email invitations to a workspace with a magic acceptance token.

CREATE TABLE workspace_invites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('admin', 'member')),
    invited_by UUID NOT NULL REFERENCES auth.users(id),
    token TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '7 days'),
    accepted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_workspace_invites_email ON workspace_invites (email);
CREATE INDEX idx_workspace_invites_token ON workspace_invites (token);
CREATE INDEX idx_workspace_invites_workspace_id ON workspace_invites (workspace_id);

ALTER TABLE workspace_invites ENABLE ROW LEVEL SECURITY;

CREATE POLICY "workspace_invites_read_own_workspace" ON workspace_invites FOR SELECT
  USING (workspace_id IN (SELECT workspace_id FROM workspace_members WHERE user_id = auth.uid()));

CREATE POLICY "workspace_invites_create_admin" ON workspace_invites FOR INSERT
  WITH CHECK (workspace_id IN (
    SELECT workspace_id FROM workspace_members
    WHERE user_id = auth.uid() AND role IN ('owner', 'admin')
  ));
