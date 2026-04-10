-- Gradata Cloud: Initial Schema
-- Run this in Supabase SQL Editor (Dashboard -> SQL -> New Query)

-- ============================================================
-- TABLES
-- ============================================================

-- Workspaces (organizations/teams)
CREATE TABLE workspaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    owner_id UUID NOT NULL REFERENCES auth.users(id),
    plan TEXT NOT NULL DEFAULT 'free' CHECK (plan IN ('free', 'pro', 'team', 'enterprise')),
    stripe_customer_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Workspace members with role-based access
CREATE TABLE workspace_members (
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'admin', 'member')),
    joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id, user_id)
);

-- Brains (one per user per workspace, identified by SDK API key)
CREATE TABLE brains (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id),
    name TEXT NOT NULL DEFAULT 'default',
    api_key TEXT NOT NULL UNIQUE DEFAULT 'gd_' || encode(gen_random_bytes(24), 'hex'),
    last_sync_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Corrections (the raw correction events from SDK)
CREATE TABLE corrections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brain_id UUID NOT NULL REFERENCES brains(id) ON DELETE CASCADE,
    session INTEGER NOT NULL,
    category TEXT NOT NULL DEFAULT 'UNKNOWN',
    severity TEXT NOT NULL DEFAULT 'minor' CHECK (severity IN ('trivial', 'minor', 'moderate', 'major', 'rewrite')),
    description TEXT NOT NULL DEFAULT '',
    draft_preview TEXT NOT NULL DEFAULT '',
    final_preview TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Lessons (graduated rules synced from SDK)
CREATE TABLE lessons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brain_id UUID NOT NULL REFERENCES brains(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'INSTINCT' CHECK (state IN ('INSTINCT', 'PATTERN', 'RULE', 'UNTESTABLE', 'ARCHIVED', 'KILLED')),
    confidence NUMERIC(4, 2) NOT NULL DEFAULT 0.0,
    fire_count INTEGER NOT NULL DEFAULT 0,
    recurrence_days INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Meta-rules (emergent rules from 3+ related rules)
CREATE TABLE meta_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brain_id UUID NOT NULL REFERENCES brains(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    source_lesson_ids UUID[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Events (raw event log synced from SDK's events.jsonl)
CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brain_id UUID NOT NULL REFERENCES brains(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT '',
    data JSONB NOT NULL DEFAULT '{}',
    tags TEXT[] NOT NULL DEFAULT '{}',
    session INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Rule patches (self-healing audit trail)
CREATE TABLE rule_patches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lesson_id UUID NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    old_description TEXT NOT NULL,
    new_description TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX idx_corrections_brain_id ON corrections(brain_id);
CREATE INDEX idx_corrections_created_at ON corrections(created_at);
CREATE INDEX idx_corrections_brain_session ON corrections(brain_id, session);
CREATE INDEX idx_lessons_brain_id ON lessons(brain_id);
CREATE INDEX idx_lessons_state ON lessons(state);
CREATE INDEX idx_events_brain_id ON events(brain_id);
CREATE INDEX idx_events_type ON events(type);
CREATE INDEX idx_events_created_at ON events(created_at);
CREATE INDEX idx_brains_user_id ON brains(user_id);
CREATE INDEX idx_brains_api_key ON brains(api_key);
CREATE INDEX idx_workspace_members_user_id ON workspace_members(user_id);

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================

ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspace_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE brains ENABLE ROW LEVEL SECURITY;
ALTER TABLE corrections ENABLE ROW LEVEL SECURITY;
ALTER TABLE lessons ENABLE ROW LEVEL SECURITY;
ALTER TABLE meta_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE events ENABLE ROW LEVEL SECURITY;
ALTER TABLE rule_patches ENABLE ROW LEVEL SECURITY;

-- Workspace: owners see their own, members see ones they belong to
CREATE POLICY workspace_owner ON workspaces
    FOR ALL USING (owner_id = auth.uid());

CREATE POLICY workspace_member_read ON workspaces
    FOR SELECT USING (
        id IN (SELECT workspace_id FROM workspace_members WHERE user_id = auth.uid())
    );

-- Workspace members: see your own memberships + admins/owners see all in their workspace
CREATE POLICY member_self ON workspace_members
    FOR SELECT USING (user_id = auth.uid());

CREATE POLICY member_admin ON workspace_members
    FOR ALL USING (
        workspace_id IN (
            SELECT workspace_id FROM workspace_members
            WHERE user_id = auth.uid() AND role IN ('owner', 'admin')
        )
    );

-- Brains: users see own brains + team members see brains in shared workspace
CREATE POLICY brain_owner ON brains
    FOR ALL USING (user_id = auth.uid());

CREATE POLICY brain_team_read ON brains
    FOR SELECT USING (
        workspace_id IN (
            SELECT workspace_id FROM workspace_members WHERE user_id = auth.uid()
        )
    );

-- Corrections/lessons/meta_rules/events/rule_patches: via brain ownership
CREATE POLICY corrections_via_brain ON corrections
    FOR ALL USING (
        brain_id IN (SELECT id FROM brains WHERE user_id = auth.uid())
        OR brain_id IN (
            SELECT b.id FROM brains b
            JOIN workspace_members wm ON wm.workspace_id = b.workspace_id
            WHERE wm.user_id = auth.uid()
        )
    );

CREATE POLICY lessons_via_brain ON lessons
    FOR ALL USING (
        brain_id IN (SELECT id FROM brains WHERE user_id = auth.uid())
        OR brain_id IN (
            SELECT b.id FROM brains b
            JOIN workspace_members wm ON wm.workspace_id = b.workspace_id
            WHERE wm.user_id = auth.uid()
        )
    );

CREATE POLICY meta_rules_via_brain ON meta_rules
    FOR ALL USING (
        brain_id IN (SELECT id FROM brains WHERE user_id = auth.uid())
        OR brain_id IN (
            SELECT b.id FROM brains b
            JOIN workspace_members wm ON wm.workspace_id = b.workspace_id
            WHERE wm.user_id = auth.uid()
        )
    );

CREATE POLICY events_via_brain ON events
    FOR ALL USING (
        brain_id IN (SELECT id FROM brains WHERE user_id = auth.uid())
        OR brain_id IN (
            SELECT b.id FROM brains b
            JOIN workspace_members wm ON wm.workspace_id = b.workspace_id
            WHERE wm.user_id = auth.uid()
        )
    );

CREATE POLICY rule_patches_via_lesson ON rule_patches
    FOR ALL USING (
        lesson_id IN (
            SELECT l.id FROM lessons l
            JOIN brains b ON b.id = l.brain_id
            WHERE b.user_id = auth.uid()
        )
    );

-- ============================================================
-- AUTO-CREATE WORKSPACE ON FIRST LOGIN
-- ============================================================

CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS trigger AS $$
BEGIN
    INSERT INTO workspaces (name, owner_id)
    VALUES (COALESCE(NEW.raw_user_meta_data->>'full_name', 'My Workspace'), NEW.id);

    INSERT INTO workspace_members (workspace_id, user_id, role)
    VALUES (
        (SELECT id FROM workspaces WHERE owner_id = NEW.id ORDER BY created_at DESC LIMIT 1),
        NEW.id,
        'owner'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();
