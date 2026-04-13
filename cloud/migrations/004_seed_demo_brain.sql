-- Gradata Cloud: Demo seed data for new signups
-- Migration 004: Seed a demo brain on signup so the dashboard isn't empty on day 1.
--
-- Creates:
--   1  brain   (name=demo-brain, domain=engineering, metadata.is_demo=true)
--   8  lessons (2 INSTINCT, 3 PATTERN, 3 RULE across 6-dim taxonomy)
--   25 corrections (spread over last 30 days, Wozniak-shaped decay)
--   4  meta-rules (referencing demo lessons)
--   6  events   (2 graduations, 1 self-heal patch, 1 meta-rule emergence, 1 convergence, 1 alert)
--
-- All rows carry an is_demo marker so users can purge them from the settings page.

-- ============================================================
-- SCHEMA ADDITIONS
-- ============================================================

-- Ensure brains has a metadata column for the is_demo flag.
ALTER TABLE brains ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

-- Ensure brains has a domain column (referenced by the app and this seed).
ALTER TABLE brains ADD COLUMN IF NOT EXISTS domain TEXT NOT NULL DEFAULT '';

-- Ensure corrections has a JSONB data column we can tag with is_demo.
ALTER TABLE corrections ADD COLUMN IF NOT EXISTS data JSONB NOT NULL DEFAULT '{}'::jsonb;

-- Ensure lessons has a JSONB data column we can tag with is_demo.
ALTER TABLE lessons ADD COLUMN IF NOT EXISTS data JSONB NOT NULL DEFAULT '{}'::jsonb;

-- Ensure meta_rules has a JSONB context/data column for demo source_lesson_ids marker.
ALTER TABLE meta_rules ADD COLUMN IF NOT EXISTS data JSONB NOT NULL DEFAULT '{}'::jsonb;

-- ============================================================
-- SEED FUNCTION
-- ============================================================

CREATE OR REPLACE FUNCTION seed_demo_brain(p_workspace_id UUID, p_user_id UUID)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_brain_id UUID;
    v_lesson_ids UUID[] := ARRAY[]::UUID[];
    v_lid UUID;
    v_i INT;
BEGIN
    -- ------------------------------------------------------------------
    -- 1 brain
    -- ------------------------------------------------------------------
    INSERT INTO brains (workspace_id, user_id, name, domain, metadata)
    VALUES (
        p_workspace_id,
        p_user_id,
        'demo-brain',
        'engineering',
        jsonb_build_object('is_demo', true, 'seeded_at', now())
    )
    RETURNING id INTO v_brain_id;

    -- ------------------------------------------------------------------
    -- 8 demo lessons (6-dim taxonomy, 2 INSTINCT + 3 PATTERN + 3 RULE)
    -- ------------------------------------------------------------------

    -- INSTINCT (2) — confidence 0.40–0.50
    INSERT INTO lessons (brain_id, category, description, state, confidence, fire_count, data)
    VALUES (
        v_brain_id,
        'Domain Fit',
        'Prefer the project''s existing util helpers over pulling new dependencies.',
        'INSTINCT', 0.42, 2,
        jsonb_build_object('is_demo', true, 'dimension', 'Domain Fit')
    )
    RETURNING id INTO v_lid;
    v_lesson_ids := v_lesson_ids || v_lid;

    INSERT INTO lessons (brain_id, category, description, state, confidence, fire_count, data)
    VALUES (
        v_brain_id,
        'Tone & Register',
        'Match the user''s tone: terse prompts want terse answers, not essays.',
        'INSTINCT', 0.48, 3,
        jsonb_build_object('is_demo', true, 'dimension', 'Tone & Register')
    )
    RETURNING id INTO v_lid;
    v_lesson_ids := v_lesson_ids || v_lid;

    -- PATTERN (3) — confidence 0.60–0.85
    INSERT INTO lessons (brain_id, category, description, state, confidence, fire_count, data)
    VALUES (
        v_brain_id,
        'Clarity & Structure',
        'Open PR descriptions with a one-line summary, then a bulleted change list.',
        'PATTERN', 0.64, 6,
        jsonb_build_object('is_demo', true, 'dimension', 'Clarity & Structure')
    )
    RETURNING id INTO v_lid;
    v_lesson_ids := v_lesson_ids || v_lid;

    INSERT INTO lessons (brain_id, category, description, state, confidence, fire_count, data)
    VALUES (
        v_brain_id,
        'Actionability',
        'When unsure, confirm assumptions with one clarifying question before acting.',
        'PATTERN', 0.76, 9,
        jsonb_build_object('is_demo', true, 'dimension', 'Actionability')
    )
    RETURNING id INTO v_lid;
    v_lesson_ids := v_lesson_ids || v_lid;

    INSERT INTO lessons (brain_id, category, description, state, confidence, fire_count, data)
    VALUES (
        v_brain_id,
        'Goal Alignment',
        'Restate the user''s goal in one sentence before proposing a multi-step plan.',
        'PATTERN', 0.82, 11,
        jsonb_build_object('is_demo', true, 'dimension', 'Goal Alignment')
    )
    RETURNING id INTO v_lid;
    v_lesson_ids := v_lesson_ids || v_lid;

    -- RULE (3) — confidence 0.90–0.95
    INSERT INTO lessons (brain_id, category, description, state, confidence, fire_count, data)
    VALUES (
        v_brain_id,
        'Factual Integrity',
        'Verify URLs and API names against source documents before citing them.',
        'RULE', 0.93, 17,
        jsonb_build_object('is_demo', true, 'dimension', 'Factual Integrity')
    )
    RETURNING id INTO v_lid;
    v_lesson_ids := v_lesson_ids || v_lid;

    INSERT INTO lessons (brain_id, category, description, state, confidence, fire_count, data)
    VALUES (
        v_brain_id,
        'Clarity & Structure',
        'Keep outbound emails under 120 words unless the user asks for long form.',
        'RULE', 0.91, 14,
        jsonb_build_object('is_demo', true, 'dimension', 'Clarity & Structure')
    )
    RETURNING id INTO v_lid;
    v_lesson_ids := v_lesson_ids || v_lid;

    INSERT INTO lessons (brain_id, category, description, state, confidence, fire_count, data)
    VALUES (
        v_brain_id,
        'Factual Integrity',
        'Run the test suite before claiming "this fixes it" — evidence before assertions.',
        'RULE', 0.95, 22,
        jsonb_build_object('is_demo', true, 'dimension', 'Factual Integrity')
    )
    RETURNING id INTO v_lid;
    v_lesson_ids := v_lesson_ids || v_lid;

    -- ------------------------------------------------------------------
    -- 25 demo corrections — Wozniak-shaped decay across 30 days.
    -- Week 1 (days 23–29 ago): 12  |  Week 2: 7  |  Week 3: 4  |  Week 4: 2
    -- ------------------------------------------------------------------

    -- Week 1 (12 corrections, days 23..29 ago) — heavy rewrite/major early
    FOR v_i IN 0..11 LOOP
        INSERT INTO corrections (brain_id, session, category, severity, description, draft_preview, final_preview, created_at, data)
        VALUES (
            v_brain_id,
            100 + v_i,
            (ARRAY['FORMAT','LOGIC','TONE','FACT','STRUCTURE','GOAL'])[1 + (v_i % 6)],
            (ARRAY['rewrite','major','major','moderate','major','rewrite','moderate','major','minor','rewrite','major','moderate'])[v_i + 1],
            (ARRAY[
                'Rewrote PR body to lead with summary line.',
                'Tightened verbose email draft from 280 -> 110 words.',
                'Removed em dashes from outbound email copy.',
                'Confirmed deploy target before running migration.',
                'Swapped hallucinated API name for the real one.',
                'Restated user goal before multi-step plan.',
                'Cited correct RFC number, not the one I guessed.',
                'Dropped unneeded "As an AI language model" preamble.',
                'Shortened bulleted list to top 3 items.',
                'Rewrote vague "handle it" into explicit steps.',
                'Fixed incorrect function signature in code snippet.',
                'Reduced softening hedge words in tone.'
            ])[v_i + 1],
            'draft preview redacted',
            'final preview redacted',
            now() - ((23 + (v_i % 7)) || ' days')::interval,
            jsonb_build_object('is_demo', true)
        );
    END LOOP;

    -- Week 2 (7 corrections, days 15..21 ago)
    FOR v_i IN 0..6 LOOP
        INSERT INTO corrections (brain_id, session, category, severity, description, draft_preview, final_preview, created_at, data)
        VALUES (
            v_brain_id,
            120 + v_i,
            (ARRAY['FORMAT','LOGIC','TONE','FACT','STRUCTURE','GOAL'])[1 + (v_i % 6)],
            (ARRAY['moderate','minor','moderate','major','minor','moderate','minor'])[v_i + 1],
            (ARRAY[
                'Matched user tone — terse request, terse reply.',
                'Dropped unsolicited alternatives after user picked one.',
                'Verified library name against package.json before suggesting.',
                'Reordered PR description: summary first, details second.',
                'Asked one clarifying question instead of five.',
                'Cut filler sentence from Slack reply.',
                'Named the exact file path instead of "the config file".'
            ])[v_i + 1],
            'draft preview redacted',
            'final preview redacted',
            now() - ((15 + (v_i % 7)) || ' days')::interval,
            jsonb_build_object('is_demo', true)
        );
    END LOOP;

    -- Week 3 (4 corrections, days 8..14 ago)
    FOR v_i IN 0..3 LOOP
        INSERT INTO corrections (brain_id, session, category, severity, description, draft_preview, final_preview, created_at, data)
        VALUES (
            v_brain_id,
            140 + v_i,
            (ARRAY['FORMAT','FACT','TONE','STRUCTURE'])[v_i + 1],
            (ARRAY['minor','moderate','trivial','minor'])[v_i + 1],
            (ARRAY[
                'Used project''s existing logger instead of print().',
                'Confirmed the migration number before writing it.',
                'Dropped extra exclamation point from reply.',
                'Bulleted follow-ups instead of one long paragraph.'
            ])[v_i + 1],
            'draft preview redacted',
            'final preview redacted',
            now() - ((8 + v_i * 2) || ' days')::interval,
            jsonb_build_object('is_demo', true)
        );
    END LOOP;

    -- Week 4 (2 corrections, days 1..5 ago)
    INSERT INTO corrections (brain_id, session, category, severity, description, draft_preview, final_preview, created_at, data)
    VALUES
        (
            v_brain_id, 160, 'TONE', 'trivial',
            'Matched user''s lowercase casual register.',
            'draft preview redacted', 'final preview redacted',
            now() - interval '4 days',
            jsonb_build_object('is_demo', true)
        ),
        (
            v_brain_id, 161, 'STRUCTURE', 'minor',
            'Led with the decision, details below.',
            'draft preview redacted', 'final preview redacted',
            now() - interval '1 days',
            jsonb_build_object('is_demo', true)
        );

    -- ------------------------------------------------------------------
    -- 4 demo meta-rules (reference lesson ids above)
    -- ------------------------------------------------------------------
    INSERT INTO meta_rules (brain_id, title, description, source_lesson_ids, data)
    VALUES
        (
            v_brain_id,
            'Evidence before assertions',
            'Across Factual Integrity and Actionability: always verify (URLs, APIs, tests) before claiming something is true or done.',
            ARRAY[v_lesson_ids[6], v_lesson_ids[8], v_lesson_ids[4]]::UUID[],
            jsonb_build_object('is_demo', true, 'source_lesson_ids_demo', true)
        ),
        (
            v_brain_id,
            'Lead with the point',
            'Across Clarity & Structure and Goal Alignment: put summary/decision on line 1, supporting detail below.',
            ARRAY[v_lesson_ids[3], v_lesson_ids[5], v_lesson_ids[7]]::UUID[],
            jsonb_build_object('is_demo', true, 'source_lesson_ids_demo', true)
        ),
        (
            v_brain_id,
            'Match the user''s register',
            'Across Tone & Register and Domain Fit: mirror terseness, formality, and tooling choices the user already uses.',
            ARRAY[v_lesson_ids[1], v_lesson_ids[2]]::UUID[],
            jsonb_build_object('is_demo', true, 'source_lesson_ids_demo', true)
        ),
        (
            v_brain_id,
            'Ask once, then act',
            'Across Actionability and Goal Alignment: resolve ambiguity with one question, then execute — don''t loop.',
            ARRAY[v_lesson_ids[4], v_lesson_ids[5]]::UUID[],
            jsonb_build_object('is_demo', true, 'source_lesson_ids_demo', true)
        );

    -- ------------------------------------------------------------------
    -- 6 demo events
    -- ------------------------------------------------------------------
    INSERT INTO events (brain_id, type, source, data, tags, session, created_at)
    VALUES
        (
            v_brain_id, 'graduation', 'demo-seed',
            jsonb_build_object('is_demo', true, 'lesson_id', v_lesson_ids[6], 'from', 'PATTERN', 'to', 'RULE'),
            ARRAY['is_demo','graduation']::TEXT[],
            145,
            now() - interval '10 days'
        ),
        (
            v_brain_id, 'graduation', 'demo-seed',
            jsonb_build_object('is_demo', true, 'lesson_id', v_lesson_ids[8], 'from', 'PATTERN', 'to', 'RULE'),
            ARRAY['is_demo','graduation']::TEXT[],
            152,
            now() - interval '6 days'
        ),
        (
            v_brain_id, 'self_heal_patch', 'demo-seed',
            jsonb_build_object(
                'is_demo', true,
                'lesson_id', v_lesson_ids[7],
                'reason', 'Auto-tightened wording after 3 high-confidence fires.'
            ),
            ARRAY['is_demo','self_heal']::TEXT[],
            155,
            now() - interval '5 days'
        ),
        (
            v_brain_id, 'meta_rule_emergence', 'demo-seed',
            jsonb_build_object(
                'is_demo', true,
                'meta_rule_title', 'Evidence before assertions',
                'source_count', 3
            ),
            ARRAY['is_demo','meta_rule']::TEXT[],
            158,
            now() - interval '3 days'
        ),
        (
            v_brain_id, 'convergence', 'demo-seed',
            jsonb_build_object(
                'is_demo', true,
                'category', 'Factual Integrity',
                'correction_rate_delta', -0.62
            ),
            ARRAY['is_demo','convergence']::TEXT[],
            160,
            now() - interval '2 days'
        ),
        (
            v_brain_id, 'alert', 'demo-seed',
            jsonb_build_object(
                'is_demo', true,
                'severity', 'info',
                'message', 'Demo brain seeded. Clear it from brain settings when you are ready.'
            ),
            ARRAY['is_demo','alert']::TEXT[],
            161,
            now() - interval '1 days'
        );

    RETURN v_brain_id;
END;
$$;

-- ============================================================
-- REPLACE handle_new_user TO CALL seed_demo_brain
-- ============================================================
--
-- The original trigger in 001_initial_schema.sql creates a workspace,
-- a membership row, and a default brain. We replace it so that instead
-- of the empty default brain it calls seed_demo_brain(), which creates
-- the demo-brain with fully populated demo data.

CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_workspace_id UUID;
BEGIN
    INSERT INTO workspaces (name, owner_id)
    VALUES (COALESCE(NEW.raw_user_meta_data->>'full_name', 'My Workspace'), NEW.id)
    RETURNING id INTO v_workspace_id;

    INSERT INTO workspace_members (workspace_id, user_id, role)
    VALUES (v_workspace_id, NEW.id, 'owner');

    -- Seed the demo brain (replaces the old empty default-brain insert).
    PERFORM seed_demo_brain(v_workspace_id, NEW.id);

    RETURN NEW;
END;
$$;

-- The trigger definition itself (on_auth_user_created) is created in
-- migration 001 and already points at handle_new_user(), so CREATE OR
-- REPLACE FUNCTION above is sufficient — no need to re-create the trigger.

-- ============================================================
-- TEST HELPER (used by local dev / docs)
-- ============================================================

CREATE OR REPLACE FUNCTION handle_new_user_test(p_user_id UUID, p_full_name TEXT DEFAULT 'Test User')
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_workspace_id UUID;
BEGIN
    INSERT INTO workspaces (name, owner_id)
    VALUES (p_full_name, p_user_id)
    RETURNING id INTO v_workspace_id;

    INSERT INTO workspace_members (workspace_id, user_id, role)
    VALUES (v_workspace_id, p_user_id, 'owner');

    RETURN seed_demo_brain(v_workspace_id, p_user_id);
END;
$$;
