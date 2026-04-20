-- =============================================================================
-- Gradata Cloud Schema v1 (Supabase / Postgres)
-- =============================================================================
-- Mirrors the critical subset of the local brain schema for multi-tenant sync.
-- Local SQLite stays the source of truth; cloud is for:
--   1. Backup / cross-device sync per tenant
--   2. Cross-tenant meta-rule distribution (visibility='global' / 'shared')
--   3. Proprietary scoring & graduation as a service
--
-- Identity model:
--   - tenant_id is a UUID matching auth.uid() from Supabase Auth.
--   - Each human/account has exactly one tenant_id.
--   - For Oliver's existing brain (tenant 402bc79c-...), his Supabase auth user
--     MUST be created with that same UUID via the admin API. See bottom of file.
--   - tenant_id IS NULL + visibility='global' => Gradata-curated shared rules.
--
-- Local tables NOT mirrored in cloud v1 (kept local-only):
--   deals, signals, facts, pipeline_snapshots, daily_metrics  (Pipedrive is source)
--   brain_embeddings, brain_fts_*                              (derived, regenerate)
--   tasks, agent_jobs, enrichment_queue                        (local execution)
--   activity_log, prep_outcomes, demo_recordings               (add when needed)
--   correction_patterns, output_classifications, entities      (v2)
--
-- Apply order:
--   1. Extensions
--   2. Tables
--   3. Indexes
--   4. RLS enable + policies
--   5. Seed Oliver (service_role)
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. Extensions
-- -----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS vector;  -- reserved for v2 embeddings


-- -----------------------------------------------------------------------------
-- 2. Tables
-- -----------------------------------------------------------------------------

-- Schema versioning (applied migrations within the cloud DB itself)
CREATE TABLE IF NOT EXISTS cloud_migrations (
    name         TEXT PRIMARY KEY,
    applied_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes        TEXT DEFAULT ''
);

-- Every tenant in the cloud. auth.uid() MUST equal tenant_id.
CREATE TABLE IF NOT EXISTS tenant_registry (
    tenant_id     UUID PRIMARY KEY,                  -- same as auth.uid()
    display_name  TEXT,
    email         TEXT UNIQUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_primary    BOOLEAN DEFAULT FALSE,             -- first tenant (Oliver)
    tier          TEXT DEFAULT 'free',               -- billing stub
    notes         TEXT DEFAULT ''
);

-- Canonical event log. JSONB data blob preserves local schema flexibility.
CREATE TABLE IF NOT EXISTS events (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL,
    local_id        BIGINT,                          -- id from local SQLite (dedup key)
    ts              TIMESTAMPTZ NOT NULL,
    session         INT,
    type            TEXT NOT NULL,
    source          TEXT,
    data            JSONB NOT NULL DEFAULT '{}'::jsonb,
    tags            JSONB NOT NULL DEFAULT '[]'::jsonb,
    scope           TEXT DEFAULT 'local',
    schema_version  INT NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, local_id)                      -- idempotent upsert key
);

-- Rules with global/shared/private visibility. tenant_id NULL => global.
CREATE TABLE IF NOT EXISTS meta_rules (
    id                      TEXT PRIMARY KEY,
    tenant_id               UUID,                     -- NULL = global
    visibility              TEXT NOT NULL DEFAULT 'private'
                            CHECK (visibility IN ('private','shared','global')),
    principle               TEXT NOT NULL,
    source_categories       TEXT,
    source_lesson_ids       TEXT,
    confidence              REAL,
    created_session         INT,
    last_validated_session  INT,
    scope                   TEXT,
    examples                TEXT,
    context_weights         TEXT,
    applies_when            TEXT,
    never_when              TEXT,
    evidence_for            TEXT,
    evidence_against        TEXT,
    ablation_status         TEXT,
    transfer_scope          TEXT,
    decay_rate              TEXT,
    activation_count        TEXT,
    last_activated          TEXT,
    source                  TEXT DEFAULT 'deterministic',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (
        (visibility = 'global'  AND tenant_id IS NULL) OR
        (visibility IN ('private','shared') AND tenant_id IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS frameworks (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID,
    visibility      TEXT NOT NULL DEFAULT 'private'
                    CHECK (visibility IN ('private','shared','global')),
    name            TEXT NOT NULL,
    times_used      INT DEFAULT 0,
    conversion_rate REAL,
    best_persona    TEXT,
    worst_persona   TEXT,
    default_for     TEXT,
    confidence      TEXT DEFAULT '[INSUFFICIENT]',
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, name)
);

CREATE TABLE IF NOT EXISTS rule_relationships (
    id            BIGSERIAL PRIMARY KEY,
    tenant_id     UUID,
    visibility    TEXT NOT NULL DEFAULT 'private'
                  CHECK (visibility IN ('private','shared','global')),
    rule_a_id     TEXT NOT NULL,
    rule_b_id     TEXT NOT NULL,
    relationship  TEXT NOT NULL,
    confidence    REAL DEFAULT 0.5,
    detected_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rule_provenance (
    id                    BIGSERIAL PRIMARY KEY,
    tenant_id             UUID NOT NULL,
    rule_id               TEXT NOT NULL,
    correction_event_id   TEXT,
    session               INT,
    ts                    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_context          TEXT
);

CREATE TABLE IF NOT EXISTS correction_severity (
    id                    BIGSERIAL PRIMARY KEY,
    tenant_id             UUID NOT NULL,
    session               INT,
    event_index           INT,
    ts                    TIMESTAMPTZ,
    category              TEXT,
    levenshtein_ratio     REAL,
    word_level_ratio      REAL,
    lines_added           INT,
    lines_removed         INT,
    severity_score        REAL,
    severity_label        TEXT,
    draft_length          INT,
    final_length          INT,
    method                TEXT DEFAULT 'text_diff',
    confidence            REAL DEFAULT 1.0,
    detail                TEXT
);

CREATE TABLE IF NOT EXISTS session_metrics (
    tenant_id                 UUID NOT NULL,
    session                   INT NOT NULL,
    date                      TEXT NOT NULL,
    session_type              TEXT NOT NULL DEFAULT 'full',
    outputs_produced          INT DEFAULT 0,
    outputs_unedited          INT DEFAULT 0,
    corrections               INT DEFAULT 0,
    first_draft_acceptance    REAL,
    correction_density        REAL,
    source_coverage           REAL,
    confidence_calibration    REAL,
    gate_pass_count           INT,
    gate_total_count          INT,
    gate_pass_rate            REAL,
    gate_result               TEXT CHECK (gate_result IN ('PASS','FAIL')),
    created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    growth_reply_rate         REAL,
    growth_deal_velocity      REAL,
    growth_pipeline_trend     REAL,
    growth_win_rate           REAL,
    PRIMARY KEY (tenant_id, session)
);

CREATE TABLE IF NOT EXISTS session_gates (
    id           BIGSERIAL PRIMARY KEY,
    tenant_id    UUID NOT NULL,
    session      INT NOT NULL,
    check_name   TEXT NOT NULL,
    passed       BOOLEAN NOT NULL,
    detail       TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_scores (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL,
    session         INT NOT NULL,
    date            TEXT NOT NULL,
    research        INT,
    quality         INT,
    process         INT,
    learning        INT,
    outcomes        INT,
    auditor_avg     REAL,
    loop_avg        REAL,
    combined_avg    REAL,
    lowest_dim      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS lesson_transitions (
    id                BIGSERIAL PRIMARY KEY,
    tenant_id         UUID NOT NULL,
    lesson_desc       TEXT NOT NULL,
    category          TEXT NOT NULL,
    old_state         TEXT NOT NULL,
    new_state         TEXT NOT NULL,
    confidence        REAL,
    fire_count        INT DEFAULT 0,
    session           INT,
    transitioned_at   TIMESTAMPTZ NOT NULL,
    path              TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS ablation_log (
    id                  BIGSERIAL PRIMARY KEY,
    tenant_id           UUID NOT NULL,
    session             INT NOT NULL,
    rule_category       TEXT NOT NULL,
    rule_description    TEXT,
    rule_confidence     REAL,
    ablated             BOOLEAN DEFAULT TRUE,
    error_recurred      BOOLEAN,
    correction_count    INT DEFAULT 0,
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    window_sessions     INT DEFAULT 1,
    window_end_session  INT
);

-- Sync bookkeeping: one row per (tenant, source) tracking last push/pull.
CREATE TABLE IF NOT EXISTS sync_state (
    tenant_id            UUID NOT NULL,
    source               TEXT NOT NULL,
    last_push_ts         TIMESTAMPTZ,
    last_pull_ts         TIMESTAMPTZ,
    last_push_session    INT,
    items_pushed         BIGINT DEFAULT 0,
    items_pulled         BIGINT DEFAULT 0,
    PRIMARY KEY (tenant_id, source)
);


-- -----------------------------------------------------------------------------
-- 3. Indexes
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_events_tenant_ts     ON events (tenant_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_events_tenant_type   ON events (tenant_id, type);
CREATE INDEX IF NOT EXISTS idx_events_session       ON events (tenant_id, session);
CREATE INDEX IF NOT EXISTS idx_events_data          ON events USING GIN (data);
CREATE INDEX IF NOT EXISTS idx_events_tags          ON events USING GIN (tags);

CREATE INDEX IF NOT EXISTS idx_meta_rules_tenant    ON meta_rules (tenant_id);
CREATE INDEX IF NOT EXISTS idx_meta_rules_vis       ON meta_rules (visibility);
CREATE INDEX IF NOT EXISTS idx_meta_rules_scope     ON meta_rules (scope);

CREATE INDEX IF NOT EXISTS idx_frameworks_tenant    ON frameworks (tenant_id);
CREATE INDEX IF NOT EXISTS idx_provenance_tenant    ON rule_provenance (tenant_id, rule_id);
CREATE INDEX IF NOT EXISTS idx_corr_tenant          ON correction_severity (tenant_id, session);
CREATE INDEX IF NOT EXISTS idx_sess_metrics_date    ON session_metrics (tenant_id, date);


-- -----------------------------------------------------------------------------
-- 4. Row-Level Security
-- -----------------------------------------------------------------------------

ALTER TABLE tenant_registry     ENABLE ROW LEVEL SECURITY;
ALTER TABLE events              ENABLE ROW LEVEL SECURITY;
ALTER TABLE meta_rules          ENABLE ROW LEVEL SECURITY;
ALTER TABLE frameworks          ENABLE ROW LEVEL SECURITY;
ALTER TABLE rule_relationships  ENABLE ROW LEVEL SECURITY;
ALTER TABLE rule_provenance     ENABLE ROW LEVEL SECURITY;
ALTER TABLE correction_severity ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_metrics     ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_gates       ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_scores        ENABLE ROW LEVEL SECURITY;
ALTER TABLE lesson_transitions  ENABLE ROW LEVEL SECURITY;
ALTER TABLE ablation_log        ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_state          ENABLE ROW LEVEL SECURITY;

-- tenant_registry: user can see + update their own row.
DROP POLICY IF EXISTS tr_self_read  ON tenant_registry;
DROP POLICY IF EXISTS tr_self_write ON tenant_registry;
CREATE POLICY tr_self_read  ON tenant_registry FOR SELECT USING (tenant_id = auth.uid());
CREATE POLICY tr_self_write ON tenant_registry FOR UPDATE
    USING (tenant_id = auth.uid()) WITH CHECK (tenant_id = auth.uid());

-- Generic per-tenant policy template (applied per table below).
-- A user sees only rows with their tenant_id. No global/shared for these.
DO $$
DECLARE
    t TEXT;
    tables TEXT[] := ARRAY[
        'events',
        'rule_provenance',
        'correction_severity',
        'session_metrics',
        'session_gates',
        'audit_scores',
        'lesson_transitions',
        'ablation_log',
        'sync_state'
    ];
BEGIN
    FOREACH t IN ARRAY tables LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I_select ON %I', t, t);
        EXECUTE format('DROP POLICY IF EXISTS %I_insert ON %I', t, t);
        EXECUTE format('DROP POLICY IF EXISTS %I_update ON %I', t, t);
        EXECUTE format('DROP POLICY IF EXISTS %I_delete ON %I', t, t);

        EXECUTE format(
            'CREATE POLICY %I_select ON %I FOR SELECT USING (tenant_id = auth.uid())',
            t, t);
        EXECUTE format(
            'CREATE POLICY %I_insert ON %I FOR INSERT WITH CHECK (tenant_id = auth.uid())',
            t, t);
        EXECUTE format(
            'CREATE POLICY %I_update ON %I FOR UPDATE USING (tenant_id = auth.uid()) WITH CHECK (tenant_id = auth.uid())',
            t, t);
        EXECUTE format(
            'CREATE POLICY %I_delete ON %I FOR DELETE USING (tenant_id = auth.uid())',
            t, t);
    END LOOP;
END $$;

-- Visibility-aware policies for meta_rules / frameworks / rule_relationships.
-- SELECT: your own rows OR visibility='global'/'shared'.
-- INSERT/UPDATE/DELETE: your own rows only; cannot create globals as a normal user.
DO $$
DECLARE
    t TEXT;
    vtables TEXT[] := ARRAY['meta_rules','frameworks','rule_relationships'];
BEGIN
    FOREACH t IN ARRAY vtables LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I_select ON %I', t, t);
        EXECUTE format('DROP POLICY IF EXISTS %I_insert ON %I', t, t);
        EXECUTE format('DROP POLICY IF EXISTS %I_update ON %I', t, t);
        EXECUTE format('DROP POLICY IF EXISTS %I_delete ON %I', t, t);

        EXECUTE format($f$
            CREATE POLICY %I_select ON %I FOR SELECT USING (
                tenant_id = auth.uid()
                OR visibility IN ('global','shared')
            )$f$, t, t);
        EXECUTE format($f$
            CREATE POLICY %I_insert ON %I FOR INSERT WITH CHECK (
                tenant_id = auth.uid()
                AND visibility IN ('private','shared')
            )$f$, t, t);
        EXECUTE format($f$
            CREATE POLICY %I_update ON %I FOR UPDATE
                USING (tenant_id = auth.uid())
                WITH CHECK (tenant_id = auth.uid() AND visibility IN ('private','shared'))
            $f$, t, t);
        EXECUTE format(
            'CREATE POLICY %I_delete ON %I FOR DELETE USING (tenant_id = auth.uid())',
            t, t);
    END LOOP;
END $$;


-- -----------------------------------------------------------------------------
-- 5. Record this migration
-- -----------------------------------------------------------------------------
INSERT INTO cloud_migrations (name, notes)
VALUES ('001_cloud_schema_v1', 'initial cloud schema + RLS')
ON CONFLICT (name) DO NOTHING;


-- =============================================================================
-- SEED: Oliver's primary tenant  (RUN WITH service_role ONLY)
-- =============================================================================
-- After creating the Supabase auth user with id = 402bc79c-1ef3-42e4-a410-52b909babfc6
-- (via admin API), run:
--
--   INSERT INTO tenant_registry (tenant_id, display_name, email, is_primary, tier)
--   VALUES (
--       '402bc79c-1ef3-42e4-a410-52b909babfc6',
--       'Oliver Le',
--       'oliver@hausgem.com',
--       TRUE,
--       'founder'
--   )
--   ON CONFLICT (tenant_id) DO NOTHING;
--
-- Seed a global meta-rule example (service_role only):
--
--   INSERT INTO meta_rules (id, tenant_id, visibility, principle, scope, confidence, source)
--   VALUES (
--       'gradata.truth_protocol.v1',
--       NULL,
--       'global',
--       'Never report unverified numbers. Cite source or mark [INSUFFICIENT].',
--       'general',
--       0.99,
--       'curated'
--   )
--   ON CONFLICT (id) DO NOTHING;
-- =============================================================================
