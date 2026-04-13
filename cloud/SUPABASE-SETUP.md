# Supabase Setup Runbook

Everything that must be configured in the Supabase dashboard for Gradata Cloud to run end-to-end. Runbook for a human — steps can't be automated.

## 1. Google OAuth provider

**Why:** Users sign in with Google from the dashboard. The frontend already calls `supabase.auth.signInWithOAuth({ provider: 'google', ... })` (see `cloud/dashboard/src/hooks/useAuth.ts`).

**Steps:**

1. Open https://console.cloud.google.com → pick (or create) the `Gradata` project
2. APIs & Services → OAuth consent screen
   - User Type: External
   - App name: `Gradata`
   - Support email: `support@gradata.ai`
   - Authorized domains: `gradata.ai`, `supabase.co`
   - Scopes: `userinfo.email`, `userinfo.profile`, `openid`
3. APIs & Services → Credentials → Create → OAuth Client ID
   - Type: Web application
   - Name: `Gradata Supabase`
   - Authorized JS origins: `https://app.gradata.ai`, `http://localhost:3000`
   - Authorized redirect URIs: `https://<supabase-project>.supabase.co/auth/v1/callback`
4. Copy the **Client ID** and **Client Secret**
5. Supabase dashboard → Authentication → Providers → Google
   - Enable
   - Paste Client ID + Client Secret
   - Save

**Verify:** Open `https://app.gradata.ai/login` → click "Continue with Google" → should bounce to accounts.google.com → back to `/dashboard` after consent.

## 2. Custom email templates

**Why:** Default Supabase emails say "Confirm your email" with a generic Supabase header. Launch-ready branding matters.

**Steps:**

1. Supabase dashboard → Authentication → Email Templates
2. For each template (Confirm signup, Magic Link, Change Email Address, Reset Password):
   - Subject: keep actionable (e.g. `"Confirm your Gradata account"`)
   - Sender name: `Gradata`
   - Body: replace with branded HTML. Use `{{ .ConfirmationURL }}` for the link, `{{ .Email }}` for the email, `{{ .Token }}` for OTP (if using).

Use the templates in `cloud/dashboard/public/email-templates/*.html` as starting points if they exist — otherwise write minimal branded markup:

```html
<!doctype html>
<html>
<body style="font-family: system-ui, sans-serif; background:#0C1120; color:#F8FAFC; padding:32px;">
  <div style="max-width:480px;margin:0 auto;">
    <h1 style="font-family: 'Space Grotesk', sans-serif;">Gradata</h1>
    <p>Click to confirm your email:</p>
    <a href="{{ .ConfirmationURL }}" style="display:inline-block;padding:10px 20px;border-radius:8px;background:linear-gradient(135deg,#3A82FF,#7C3AED);color:#fff;text-decoration:none;">
      Confirm email
    </a>
    <p style="color:#8895A7;margin-top:32px;font-size:12px;">If you didn't sign up, ignore this email.</p>
  </div>
</body>
</html>
```

3. Save. Test by triggering a signup / magic link / password reset locally and checking the inbox.

## 3. Row-Level Security (RLS) for new tables

**Why:** The new `meta_rules`, `rule_patches`, `events` tables need policies so users only see their own data.

The initial schema (migration `001_initial_schema.sql`) already created these tables — double-check the RLS policies are in place:

```sql
-- meta_rules: user can SELECT their own brain's meta-rules
CREATE POLICY "meta_rules_read_own" ON meta_rules FOR SELECT
  USING (brain_id IN (SELECT id FROM brains WHERE user_id = auth.uid()));

-- rule_patches: user can SELECT patches for their own lessons
CREATE POLICY "rule_patches_read_own" ON rule_patches FOR SELECT
  USING (lesson_id IN (
    SELECT l.id FROM lessons l
    JOIN brains b ON b.id = l.brain_id
    WHERE b.user_id = auth.uid()
  ));

-- events: user can SELECT events for their own brain
CREATE POLICY "events_read_own" ON events FOR SELECT
  USING (brain_id IN (SELECT id FROM brains WHERE user_id = auth.uid()));
```

Run these in Supabase → SQL Editor if missing. The cloud backend uses the service role key (bypasses RLS), but direct dashboard queries (if we ever add them) need the policies.

**Verify:** Open Supabase → Table Editor → meta_rules → Policies tab. Should show at least one SELECT policy scoped to `auth.uid()`.

## 4. Database webhook for sync → events telemetry (optional)

If you want Sentry-style observability on sync endpoint traffic, Supabase → Database → Webhooks → Create:

- Table: `events`
- Events: Insert
- Method: POST
- URL: `https://api.gradata.ai/internal/event-firehose` (only if we build it — skip for now)

## 5. Auth settings to verify

Supabase → Authentication → URL Configuration:
- Site URL: `https://app.gradata.ai`
- Redirect URLs: add `https://app.gradata.ai/dashboard`, `https://app.gradata.ai/**`, `http://localhost:3000/**`
- JWT expiry: keep default (3600s / 1h)
- Refresh token rotation: Enabled

## 6. Auto-create workspace on signup

The existing trigger (per `project_s104_handoff`) creates a workspace + brain row on user signup. Verify it's installed:

```sql
SELECT * FROM pg_trigger WHERE tgname LIKE '%handle_new_user%';
```

Should return at least one row. If missing, re-run the relevant migration.
