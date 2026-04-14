# Cloud Operations Index

Single entry point for running, deploying, and operating Gradata Cloud. Everything a non-Oliver human would need to keep the service alive.

## Repo layout

```
cloud/
├── app/                    FastAPI backend (Railway)
├── dashboard/              Next.js 16 dashboard (Cloudflare Pages)
├── migrations/             Supabase schema
├── tests/                  Backend pytest suite (58 tests)
├── Dockerfile              Railway build
├── pyproject.toml
├── railway.toml
├── OPS.md                  ← this file
├── SENTRY-SETUP.md         ← error tracking
├── SUPABASE-SETUP.md       ← Google OAuth, email templates, RLS
├── RAILWAY-ENV.md          ← complete backend env var list
└── dashboard/
    ├── CLOUDFLARE-PAGES.md ← frontend deploy settings
    └── ...
```

## Where each thing runs

| Surface | Host | URL | Build output |
|---|---|---|---|
| Marketing site | Cloudflare Pages | `gradata.ai` | Vite SPA (tbd migrate to Next.js for SEO) |
| Dashboard | Cloudflare Pages | `app.gradata.ai` | Next.js 16 static export → `cloud/dashboard/out/` |
| API backend | Railway | `api.gradata.ai` | Dockerfile → uvicorn |
| Database + auth | Supabase | `<project>.supabase.co` | Managed Postgres + RLS |
| Error tracking | Sentry | `sentry.io/organizations/gradata` | Backend + frontend projects |
| Billing | Stripe | `dashboard.stripe.com` | Products: Cloud $29, Team $99 |

## First-time setup

Follow in order:

1. **Supabase project** — run migrations, configure Google OAuth, set RLS. See `SUPABASE-SETUP.md`.
2. **Stripe** — create Cloud + Team products, register webhook to `api.gradata.ai/api/v1/billing/webhook`. See `RAILWAY-ENV.md` §Stripe.
3. **Sentry** — create `gradata-cloud` (Python) and `gradata-dashboard` (React) projects. Grab DSNs. See `SENTRY-SETUP.md`.
4. **Railway** — create service, paste env vars from `RAILWAY-ENV.md`, connect GitHub. Railway auto-deploys on push to `main`.
5. **Cloudflare Pages** — create project for `dashboard`, set build command + output dir + env vars. See `dashboard/CLOUDFLARE-PAGES.md`.
6. **DNS** — in Cloudflare DNS for `gradata.ai`:
   - `api` CNAME → `<railway-service>.railway.app`
   - `app` CNAME → `<pages-project>.pages.dev`
7. **Custom domains** — in Railway and Cloudflare Pages, add the custom domains. SSL certs provision within minutes.

## Day-to-day

**Deploy backend:** merge to `main` → Railway auto-builds from `cloud/Dockerfile` → production in 2–3 min.

**Deploy dashboard:** merge to `main` → Cloudflare Pages runs `pnpm install && pnpm build` in `cloud/dashboard/` → production in 2–3 min.

**Run backend tests locally:**
```bash
cd cloud
python -m pytest tests/ -q
```
All 58 tests should pass in <20s (no real Supabase/Stripe needed — fully mocked).

**Run dashboard locally:**
```bash
cd cloud/dashboard
cp .env.example .env.local  # fill in Supabase URL + anon key + API URL
CI=true pnpm install        # clean install
pnpm dev                    # http://localhost:3000
```

**Run a migration:** Supabase → SQL Editor → paste the SQL → run. We don't have a migration tool; migrations are hand-run. Track them in `cloud/migrations/` with sequential numbering.

## On call

**Backend down:**
1. Railway dashboard → `gradata-production` → Deployments → check for red deploys
2. Logs → look for stack traces
3. If Sentry is wired (see `SENTRY-SETUP.md`), errors show in Sentry project `gradata-cloud` automatically
4. Rollback: Railway → Deployments → select a healthy deploy → Redeploy

**Dashboard down:**
1. Cloudflare Pages → `gradata-dashboard` → Deployments → inspect latest build
2. Build failure? Check build logs for TypeScript / linting errors
3. Serving 500/blank? Check `NEXT_PUBLIC_*` env vars — Next.js inlines these AT BUILD TIME, so missing vars = empty Supabase client on the live site
4. Rollback: Cloudflare Pages → select previous successful deployment → promote

**Database issue:**
1. Supabase → Logs → check for slow queries / RLS rejections
2. If RLS policy is wrong, `auth.uid()` returns null in query — users see empty results
3. Re-run RLS policies from `SUPABASE-SETUP.md` §3 if needed

**Stripe webhook failing:**
1. Stripe → Developers → Webhooks → select endpoint → Webhook attempts
2. Signature verification failure = `GRADATA_STRIPE_WEBHOOK_SECRET` mismatch on Railway
3. Retry manually from Stripe dashboard once the secret is fixed

## Emergency contacts

- Oliver (founder): `oliver@gradata.ai`
- Supabase support: https://supabase.com/dashboard/support
- Railway support: https://railway.app/help
- Cloudflare Pages support: through dashboard → Help
- Stripe support: https://support.stripe.com

## Versioning

- SDK (open source): PyPI `gradata` — bump `sdk/pyproject.toml` version, `uv build`, `uv publish`
- Cloud backend: semver tagged in `cloud/pyproject.toml`. Not a published artifact — only runs on Railway.
- Dashboard: `cloud/dashboard/package.json` — version is informational, no registry publish.
