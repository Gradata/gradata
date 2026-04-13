# Railway Environment Variables

Complete list of env vars for the `gradata-production` service on Railway. Everything here goes in Railway → Variables, not in the repo.

## Required (backend will 500 on boot without these)

| Var | Source | Purpose |
|-----|--------|---------|
| `GRADATA_SUPABASE_URL` | Supabase dashboard → Settings → API | Database + auth base URL |
| `GRADATA_SUPABASE_ANON_KEY` | Supabase → Settings → API | Public anon key (RLS-gated) |
| `GRADATA_SUPABASE_SERVICE_KEY` | Supabase → Settings → API | Service role key (bypasses RLS — server-only) |
| `GRADATA_SUPABASE_JWT_KEY` | Supabase → Settings → API → JWT Secret | For HS256 JWT verification fallback |

## Required for Stripe billing

| Var | Source | Purpose |
|-----|--------|---------|
| `GRADATA_STRIPE_SECRET_KEY` | Stripe → Developers → API keys | Server-side API calls |
| `GRADATA_STRIPE_WEBHOOK_SECRET` | Stripe → Developers → Webhooks → endpoint | Verifies inbound webhook signatures |
| `GRADATA_STRIPE_PRICE_ID_CLOUD` | Stripe → Products → Cloud $29 → Pricing | `price_...` for Checkout sessions |
| `GRADATA_STRIPE_PRICE_ID_TEAM` | Stripe → Products → Team $99 → Pricing | `price_...` for Checkout sessions |

**Stripe products to create** (Stripe dashboard → Products → Add product):

- **Cloud** · recurring · $29.00 USD / month · description "Per-user plan with rules + trends"
- **Team** · recurring · $99.00 USD / month · description "Up to 15 seats with leaderboard and team analytics"
- **Enterprise** — do NOT create in Stripe. Enterprise goes through sales (the backend rejects it on the checkout route).

**Webhook endpoint to register** (Stripe → Developers → Webhooks → Add endpoint):

- URL: `https://api.gradata.ai/api/v1/billing/webhook`
- Events: `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_failed`, `checkout.session.completed`
- Copy the signing secret → `GRADATA_STRIPE_WEBHOOK_SECRET`

## Optional — Sentry error tracking

| Var | Purpose |
|-----|---------|
| `GRADATA_SENTRY_DSN` | DSN from Sentry project `gradata-cloud`. Unset = Sentry disabled (prod-safe) |
| `GRADATA_SENTRY_TRACES_SAMPLE_RATE` | Default `0.1`. Drop to `0.02` if cost becomes an issue |
| `GRADATA_SENTRY_RELEASE` | Override the release tag. Default uses `RAILWAY_GIT_COMMIT_SHA` |

## Optional — App config

| Var | Default | Purpose |
|-----|---------|---------|
| `GRADATA_ENVIRONMENT` | `development` | Set to `production` on Railway |
| `GRADATA_LOG_LEVEL` | `INFO` | Use `DEBUG` only when actively diagnosing |
| `GRADATA_CORS_ORIGINS` | `http://localhost:3000,https://app.gradata.ai` | Comma-separated allow-list |

## Auto-provided by Railway

Railway sets these for you — reference them in code, don't set them:

- `RAILWAY_GIT_COMMIT_SHA` — current deploy SHA (Sentry uses this for release tag)
- `PORT` — the port uvicorn should bind to (Dockerfile uses this)

## How to set them

Railway dashboard → `gradata-production` service → Variables → Raw Editor → paste as:

```
GRADATA_SUPABASE_URL=https://xxx.supabase.co
GRADATA_SUPABASE_ANON_KEY=...
GRADATA_SUPABASE_SERVICE_KEY=...
GRADATA_SUPABASE_JWT_KEY=...
GRADATA_STRIPE_SECRET_KEY=sk_live_...
GRADATA_STRIPE_WEBHOOK_SECRET=whsec_...
GRADATA_STRIPE_PRICE_ID_CLOUD=price_...
GRADATA_STRIPE_PRICE_ID_TEAM=price_...
GRADATA_SENTRY_DSN=https://...@sentry.io/...
GRADATA_ENVIRONMENT=production
```

Railway will redeploy automatically. Watch logs for:

```
INFO:app.sentry_init:Sentry initialized: environment=production release=...
```

and confirm the app started without missing-env errors.

## Verify locally

```bash
cd cloud
cp .env.example .env  # if .env.example exists
# fill in dev values
python -m pytest tests/ -q
```

Tests must continue to pass. Tests mock Supabase + Stripe so they don't need real credentials.
