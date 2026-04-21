# Cloud schema v2 — Postgres as monolith

Apply after `cloud_schema.sql` v1. This upgrade lets Supabase replace
Redis (cache), Kafka (queue), Elasticsearch (search), and Pinecone
(vectors) for gradata-cloud workloads — no new vendors.

Design goal: one Postgres instance, RLS-isolated per tenant, carrying
the cloud-side visualization and sharing workloads. Local SQLite stays
the source of truth and runs graduation, synthesis, and rule-to-hook
promotion locally. Cloud is a downstream reflection — it mirrors events
and rules for dashboards, team sharing, and managed backups, but does
not gate or re-run the learning loop.

## What v2 adds

| Workload | Replaces | Mechanism |
|---|---|---|
| Full-text search | Elasticsearch | `tsvector` generated columns + GIN indexes on `events` and `meta_rules` |
| Semantic search | Pinecone / Qdrant | `pgvector` + HNSW index on `meta_rules.embedding` |
| Work queue | Kafka / RabbitMQ | `sync_queue` table + `FOR UPDATE SKIP LOCKED` claim function |
| Ephemeral cache | Redis | `UNLOGGED` `tenant_cache` table (RLS-scoped) |

Every addition is idempotent — re-runs are safe.

### Durability note — `tenant_cache` is UNLOGGED

`UNLOGGED` tables skip the WAL: ~2–3× faster writes, but **all rows are
truncated on crash, unclean shutdown, or replica promotion**. This is the
right choice for a cache (lose state, fall back to recompute), but never
store data here that cannot be re-derived. If you later add durable
per-tenant settings (e.g. feature flags), put them in a regular table.

### Text-extraction note — JSON-ish columns in `meta_rules.search_tsv`

`meta_rules.scope` and `meta_rules.examples` are stored as JSON-encoded
TEXT. The v2 tsvector feeds them to `to_tsvector('english', ...)` as-is,
which tokenizes brace/quote punctuation alongside real content. Keyword
recall is still usable, but for cleaner ranking extract the string fields
first (e.g. `coalesce(examples::jsonb->>'text','')`) and rebuild the
generated column.

## Apply order

1. Studio → SQL Editor → new query
2. Paste the SQL below
3. Run
4. Expect one new row in `cloud_migrations` (`002_cloud_monolith_v2`) plus
   `pg_trgm` extension enabled, 2 tsvector columns, 1 HNSW index, and 2
   new tables (`sync_queue`, `tenant_cache`) with RLS policies.

## SQL

```sql
-- =============================================================================
-- Gradata Cloud Schema v2 — Postgres-as-monolith upgrade
-- Apply after cloud_schema.sql. All operations are idempotent.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. Extensions
-- -----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS pg_trgm;
-- pgvector, uuid-ossp, pgcrypto are already enabled in v1.


-- -----------------------------------------------------------------------------
-- 2. Full-text search (Elasticsearch replacement)
-- -----------------------------------------------------------------------------

ALTER TABLE events
    ADD COLUMN IF NOT EXISTS search_tsv tsvector
    GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(type, '')),       'A') ||
        setweight(to_tsvector('english', coalesce(source, '')),     'B') ||
        setweight(to_tsvector('english', coalesce(data::text, '')), 'C')
    ) STORED;

CREATE INDEX IF NOT EXISTS idx_events_tsv
    ON events USING GIN (search_tsv);

CREATE INDEX IF NOT EXISTS idx_events_type_trgm
    ON events USING GIN (type gin_trgm_ops);

ALTER TABLE meta_rules
    ADD COLUMN IF NOT EXISTS search_tsv tsvector
    GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(principle, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(scope, '')),     'B') ||
        setweight(to_tsvector('english', coalesce(examples, '')),  'C')
    ) STORED;

CREATE INDEX IF NOT EXISTS idx_meta_rules_tsv
    ON meta_rules USING GIN (search_tsv);


-- -----------------------------------------------------------------------------
-- 3. Vector embeddings (Pinecone replacement)
-- -----------------------------------------------------------------------------
-- 768 dims covers all-MiniLM-L6-v2, nomic-embed-text, and most OSS embeddings.

ALTER TABLE meta_rules
    ADD COLUMN IF NOT EXISTS embedding vector(768);

CREATE INDEX IF NOT EXISTS idx_meta_rules_embedding_hnsw
    ON meta_rules USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);


-- -----------------------------------------------------------------------------
-- 4. Sync queue (Kafka replacement)
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sync_queue (
    id             BIGSERIAL PRIMARY KEY,
    tenant_id      UUID NOT NULL,
    kind           TEXT NOT NULL,
    payload_ref    BIGINT,
    enqueued_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    claimed_at     TIMESTAMPTZ,
    claimed_by     TEXT,
    completed_at   TIMESTAMPTZ,
    attempts       INT NOT NULL DEFAULT 0,
    last_error     TEXT
);

CREATE INDEX IF NOT EXISTS idx_sync_queue_tenant_pending
    ON sync_queue (tenant_id, enqueued_at)
    WHERE completed_at IS NULL;

ALTER TABLE sync_queue ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS sync_queue_select ON sync_queue;
DROP POLICY IF EXISTS sync_queue_insert ON sync_queue;
DROP POLICY IF EXISTS sync_queue_update ON sync_queue;
DROP POLICY IF EXISTS sync_queue_delete ON sync_queue;

CREATE POLICY sync_queue_select ON sync_queue FOR SELECT USING (tenant_id = auth.uid());
CREATE POLICY sync_queue_insert ON sync_queue FOR INSERT WITH CHECK (tenant_id = auth.uid());
CREATE POLICY sync_queue_update ON sync_queue FOR UPDATE
    USING (tenant_id = auth.uid()) WITH CHECK (tenant_id = auth.uid());
CREATE POLICY sync_queue_delete ON sync_queue FOR DELETE USING (tenant_id = auth.uid());

-- Workers claim up to N pending items lock-free.
CREATE OR REPLACE FUNCTION sync_queue_claim(p_worker TEXT, p_limit INT DEFAULT 32)
RETURNS TABLE (id BIGINT, tenant_id UUID, kind TEXT, payload_ref BIGINT)
LANGUAGE sql
AS $$
    WITH claimed AS (
        SELECT q.id FROM sync_queue q
        WHERE q.completed_at IS NULL AND q.claimed_at IS NULL
          AND q.tenant_id = auth.uid()
        ORDER BY q.enqueued_at
        LIMIT p_limit
        FOR UPDATE SKIP LOCKED
    )
    UPDATE sync_queue q
       SET claimed_at = NOW(), claimed_by = p_worker, attempts = q.attempts + 1
      FROM claimed c
     WHERE q.id = c.id
     RETURNING q.id, q.tenant_id, q.kind, q.payload_ref;
$$;


-- -----------------------------------------------------------------------------
-- 5. UNLOGGED per-tenant cache (Redis replacement)
-- -----------------------------------------------------------------------------

CREATE UNLOGGED TABLE IF NOT EXISTS tenant_cache (
    tenant_id   UUID NOT NULL,
    key         TEXT NOT NULL,
    value       JSONB NOT NULL,
    expires_at  TIMESTAMPTZ,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, key)
);

CREATE INDEX IF NOT EXISTS idx_tenant_cache_expires
    ON tenant_cache (expires_at)
    WHERE expires_at IS NOT NULL;

ALTER TABLE tenant_cache ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_cache_select ON tenant_cache;
DROP POLICY IF EXISTS tenant_cache_insert ON tenant_cache;
DROP POLICY IF EXISTS tenant_cache_update ON tenant_cache;
DROP POLICY IF EXISTS tenant_cache_delete ON tenant_cache;

CREATE POLICY tenant_cache_select ON tenant_cache FOR SELECT USING (tenant_id = auth.uid());
CREATE POLICY tenant_cache_insert ON tenant_cache FOR INSERT WITH CHECK (tenant_id = auth.uid());
CREATE POLICY tenant_cache_update ON tenant_cache FOR UPDATE
    USING (tenant_id = auth.uid()) WITH CHECK (tenant_id = auth.uid());
CREATE POLICY tenant_cache_delete ON tenant_cache FOR DELETE USING (tenant_id = auth.uid());


-- -----------------------------------------------------------------------------
-- 6. Record migration
-- -----------------------------------------------------------------------------
INSERT INTO cloud_migrations (name, notes)
VALUES ('002_cloud_monolith_v2', 'pg_trgm + tsvector + pgvector HNSW + SKIP LOCKED queue + UNLOGGED cache')
ON CONFLICT (name) DO NOTHING;
```

## Verification

```sql
-- Should return 002_cloud_monolith_v2
SELECT name FROM cloud_migrations WHERE name = '002_cloud_monolith_v2';

-- Should return a tsvector
SELECT search_tsv FROM events LIMIT 1;

-- Should return '{pg_trgm,vector,uuid-ossp,pgcrypto}' superset
SELECT extname FROM pg_extension ORDER BY extname;

-- Should find new policies
SELECT tablename, policyname FROM pg_policies
 WHERE tablename IN ('sync_queue','tenant_cache') ORDER BY tablename, policyname;
```

## SDK wiring (future follow-up)

- Full-text: add `cloud_search(q, limit)` to `gradata.cloud.client` using
  `ts_rank_cd(search_tsv, plainto_tsquery('english', $1))`.
- Vectors: when local lessons get embeddings, push them alongside the rule
  row; retrieval uses `embedding <=> query_embedding LIMIT k`.
- Queue: `cloud_sync.push()` currently ignores the queue; a later worker
  can drain it via `SELECT * FROM sync_queue_claim('worker-1', 32)`.
- Cache: `rule_enforcement` per-tenant memoization can move off process
  memory onto `tenant_cache` when running multi-instance.

None of the above is blocking — the schema is forward-compatible. v2 can
land and sit idle until a specific feature uses it.
