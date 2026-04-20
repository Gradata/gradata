-- =============================================================================
-- RLS smoke test — run in Supabase SQL editor with service_role DISABLED
-- (i.e. as an authenticated user via the API, not the SQL console).
-- =============================================================================
-- The console runs as postgres (bypass RLS), so it will NOT reveal RLS bugs.
-- Use the Supabase CLI `supabase test` or the REST API with two different
-- JWT tokens (userA, userB) to exercise these queries.
--
-- Expected behavior:
--   userA inserts a private rule  -> userA sees it, userB does NOT
--   userA inserts a 'shared' rule -> userB sees it
--   userB cannot UPDATE userA's rows
--   userB cannot DELETE userA's rows
--   Neither user can INSERT a visibility='global' row
-- =============================================================================

-- As userA:
-- INSERT INTO meta_rules (id, tenant_id, visibility, principle)
-- VALUES ('test.userA.private.1', auth.uid(), 'private', 'only I see this');

-- As userA:
-- INSERT INTO meta_rules (id, tenant_id, visibility, principle)
-- VALUES ('test.userA.shared.1', auth.uid(), 'shared', 'both users see this');

-- As userB — must return ZERO rows for userA.private.1:
-- SELECT id, visibility FROM meta_rules WHERE id = 'test.userA.private.1';

-- As userB — must return ONE row for userA.shared.1:
-- SELECT id, visibility FROM meta_rules WHERE id = 'test.userA.shared.1';

-- As userB — must FAIL (RLS violation) on userA's row:
-- UPDATE meta_rules SET confidence = 0.1 WHERE id = 'test.userA.private.1';

-- Neither user — must FAIL (CHECK + policy both block):
-- INSERT INTO meta_rules (id, tenant_id, visibility, principle)
-- VALUES ('test.cant.do.global', NULL, 'global', 'globals require service_role');

-- Clean up (as each user for their own rows):
-- DELETE FROM meta_rules WHERE id LIKE 'test.%';
