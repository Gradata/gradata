# Cloudflare Pages Deploy

This dashboard is a Next.js 16 static export. Cloudflare Pages serves the
pre-rendered HTML + assets; there is no Node runtime at the edge.

## Pages project settings

- **Framework preset**: Next.js (Static HTML Export)
- **Build command**: `pnpm --filter dashboard build`  (or `cd cloud/dashboard && pnpm build`)
- **Build output directory**: `cloud/dashboard/out`
- **Root directory**: `/`
- **Node version**: 20.x

## Environment variables (Production)

| Var | Required | Notes |
|-----|----------|-------|
| `NEXT_PUBLIC_SUPABASE_URL` | yes | https://<project>.supabase.co |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | yes | anon key from Supabase dashboard |
| `NEXT_PUBLIC_API_URL` | yes | https://api.gradata.ai or Railway URL |
| `NEXT_PUBLIC_SENTRY_DSN` | no | enables error tracking |
| `NEXT_PUBLIC_SENTRY_ENVIRONMENT` | no | defaults to `production` |
| `NEXT_PUBLIC_SENTRY_RELEASE` | no | defaults to `gradata-dashboard@dev` |
| `SENTRY_AUTH_TOKEN` | no | build-time only, enables source-map upload |
| `SENTRY_ORG` | no | defaults to `gradata` |
| `SENTRY_PROJECT` | no | defaults to `gradata-dashboard` |

**Important**: `NEXT_PUBLIC_*` vars are inlined at build time. After
changing any of them you must trigger a rebuild (push a commit or use
the Cloudflare "Retry deployment" button).

## Verifying the deploy

1. Open `app.gradata.ai` → should redirect to `/login`
2. Sign in / sign up → lands on `/dashboard`
3. Dashboard renders KPI strip, decay curve, graduation pipeline, rules,
   categories, meta-rules, activity, privacy, A/B proof, methodology link
4. Browser console shows `[sentry] initialized env=production release=...`
   (or `[sentry] disabled: ...` if DSN not set — prod-safe)
5. Open Sentry dashboard, trigger a React error (e.g. dev-mode bad prop),
   confirm the event arrives

## Local development

```bash
cd cloud/dashboard
pnpm install
cp .env.local.example .env.local  # fill in Supabase/API URL
pnpm dev                           # http://localhost:3000
```

## Notes on static export

- Dynamic routes like `/brains/[id]` work as client-side rendered (data
  fetched after hydration). No server-side generation needed.
- Sentry server/edge configs are stubbed — static export has no runtime
  for them.
- Fonts load via Google CSS (`<link>` in root layout) rather than
  `next/font/google`. Turbopack's font resolver conflicts with static
  export in Next 16.2; CSS `@import` is the stable path.
