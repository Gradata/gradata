# Applying cloud_schema.sql to Supabase

Step-by-step. Do this BEFORE wiring cloud_sync.py.

Rule: no tokens, keys, or passwords live in this repo. Store them in 1Password
under `Supabase / gradata-cloud-prod`. At runtime, `cloud_sync.py` reads them
from env vars.

## 1. Create the Supabase project

- Studio: https://supabase.com
- Project name: `gradata-cloud-prod`
- Region: closest to you
- DB pw: strong random, store in 1Password, never commit
- Enable Auth + Database

## 2. Apply the schema

1. Studio -> SQL Editor -> new query
2. Paste `src/gradata/_migrations/cloud_schema.sql`
3. Run

Expect: 13 `CREATE TABLE`, 13 `ENABLE ROW LEVEL SECURITY`, around 48 policies,
and one row in `cloud_migrations` (`001_cloud_schema_v1`).

## 3. Create Oliver's auth user with a pinned UUID

Critical: Oliver's `auth.users.id` MUST equal his local tenant UUID
`402bc79c-1ef3-42e4-a410-52b909babfc6`. Otherwise RLS blocks him from his
own data.

Do this via the Studio -> Authentication -> Users -> "Add user" flow only
if the Studio UI exposes a user-id override. If it does NOT, use the admin
REST endpoint `/auth/v1/admin/users` with the service role token from
1Password, setting the body field `id` to the UUID above and `email_confirm`
to true. Keep the token in an env var, never paste it in a file.

After the auth user exists, in SQL Editor run:

```sql
INSERT INTO tenant_registry (tenant_id, display_name, email, is_primary, tier)
VALUES (
    '402bc79c-1ef3-42e4-a410-52b909babfc6',
    'Oliver Le',
    'oliver@hausgem.com',
    TRUE,
    'founder'
) ON CONFLICT (tenant_id) DO NOTHING;
```

## 4. Seed global meta-rules (service_role only)

Global rules live at `tenant_id IS NULL` + `visibility='global'`. RLS blocks
normal users from inserting these -- use service_role in SQL Editor:

```sql
INSERT INTO meta_rules (id, tenant_id, visibility, principle, scope, confidence, source)
VALUES
('gradata.truth_protocol.v1', NULL, 'global',
 'Never report unverified numbers. Cite source or mark [INSUFFICIENT].',
 'general', 0.99, 'curated'),
('gradata.quality_gates.v1', NULL, 'global',
 'Every deliverable passes quality_gates before sending.',
 'general', 0.99, 'curated')
ON CONFLICT (id) DO NOTHING;
```

## 5. Verify RLS

The SQL Editor bypasses RLS (runs as postgres). Real verification needs a
second signed-in user. Flow:

1. Studio -> Authentication -> Users -> add `test-tenant@example.com` with
   a throwaway pw from 1Password. Let Supabase assign a fresh UUID.
2. Insert a `tenant_registry` row for that UUID.
3. Using either the REST API or the Supabase JS client with that user's
   session, try to `SELECT * FROM events` -- must return 0 rows.
4. Walk `src/gradata/_migrations/cloud_rls_test.sql` end-to-end.

If any cross-tenant read succeeds, stop. Fix the policy before continuing.

## 6. Record the project URL + anon key locally

The anon key is public-safe (RLS enforces isolation) but still kept out of
git to avoid cross-project confusion.

1. In Studio -> Project Settings -> API, copy the project URL and the
   `anon` public key.
2. Store the anon key in 1Password.
3. Create `brain/.cloud.json` on your machine with two fields:
   `project_url`, `anon_key`, and `schema_version`.
4. Add `brain/.cloud.json` to `.gitignore`.

The `service_role` key NEVER leaves 1Password. `cloud_sync.py` reads it from
an env var loaded per shell via `op read` at run-time.

## 7. Pre-flight before cloud_sync.py

Confirm:
- [ ] `cloud_migrations` has `001_cloud_schema_v1`
- [ ] `tenant_registry` has Oliver's row
- [ ] At least one `visibility='global'` meta_rule exists
- [ ] Test tenant verified: cannot see Oliver's rows
- [ ] `brain/.cloud.json` written locally, present in `.gitignore`

Then we wire `cloud_sync.py` to push/pull deltas.
