# Cloudflare Pages Deploy

This dashboard is a Next.js 16 static export. Cloudflare Pages serves the
pre-rendered HTML + assets; there is no Node runtime at the edge.

## Pages project settings

Configure these in the Cloudflare dashboard (Workers & Pages → gradata-dashboard
→ Settings → Builds & deployments):

- **Project name**: `gradata-dashboard`
- **Production branch**: `main` (or `worktree-dashboard-nextjs-rebuild` while in flight)
- **Framework preset**: Next.js (Static HTML Export) — or "None"; the build
  command below works either way
- **Root directory**: `/` (repo root)
- **Build command**: `cd cloud/dashboard && pnpm install --frozen-lockfile && pnpm build`
- **Build output directory**: `cloud/dashboard/out`
- **Node version**: 20.x  (set `NODE_VERSION=20` env var, or add `.nvmrc`)
- **Compatibility date**: 2026-04-12 (matches `wrangler.toml`)

`public/_headers` and `public/_redirects` are picked up automatically — Next.js
copies the entire `public/` directory into the build output, and Cloudflare
Pages reads them from the deploy root. `wrangler.toml` is optional; it lets you
deploy via `wrangler pages deploy` from CI without re-entering the settings.

## Custom domain

- **Domain**: `app.gradata.ai`
- **DNS**: Cloudflare-managed. Add a `CNAME` record:
  - Name: `app`
  - Target: `<project>.pages.dev` (e.g. `gradata-dashboard.pages.dev`)
  - Proxy status: Proxied (orange cloud)
- Cloudflare auto-issues a TLS cert. HSTS is enforced via `_headers`.

The marketing site at `gradata.ai` is a separate Pages project — do not
collide with it. The backend at `api.gradata.ai` is Railway (FastAPI), not
Cloudflare Pages.

## Environment variables (Production)

Set these in Cloudflare dashboard → Settings → Environment variables.
`NEXT_PUBLIC_*` vars are inlined at build time — after changing any of them
you must trigger a rebuild (push a commit or use the "Retry deployment" button).

| Var | Required | Notes |
|-----|----------|-------|
| `NEXT_PUBLIC_SUPABASE_URL` | yes | https://<project>.supabase.co |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | yes | anon key from Supabase dashboard |
| `NEXT_PUBLIC_API_URL` | yes | https://api.gradata.ai (or Railway URL while staging) |
| `NEXT_PUBLIC_SENTRY_DSN` | no | enables error tracking |
| `NEXT_PUBLIC_SENTRY_ENVIRONMENT` | no | defaults to `production` |
| `NEXT_PUBLIC_SENTRY_RELEASE` | no | defaults to `gradata-dashboard@dev` |
| `SENTRY_AUTH_TOKEN` | no | build-time only, enables source-map upload |
| `SENTRY_ORG` | no | defaults to `gradata` |
| `SENTRY_PROJECT` | no | defaults to `gradata-dashboard` |
| `NODE_VERSION` | recommended | `20` (or use `.nvmrc`) |

See `.env.example` for the canonical list with placeholders. Copy it to
`.env.local` for local dev — never commit `.env.local`.

## Security headers (`public/_headers`)

The `_headers` file ships:

- HSTS (1 year, includeSubDomains, preload)
- `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy` disables FLoC, geolocation, camera, mic, payment, etc.
- CSP allows: self, Supabase (`*.supabase.co` + WSS for realtime), backend
  (`api.gradata.ai`, `gradata-production.up.railway.app`), Sentry
  (`*.ingest.sentry.io`), Google Fonts (`fonts.googleapis.com` +
  `fonts.gstatic.com`). `script-src` includes `'unsafe-inline'` and
  `'unsafe-eval'` (sadly required for Next.js hydration + Turbopack).
- `/_next/static/*` cached `immutable` for 1 year (hashed filenames)

## Redirects (`public/_redirects`)

- `/brains/*` → `/brain?id=:splat` (legacy compat, 301)
- `/app/*` → `/:splat` (subdomain root compat, 301)

No SPA catchall is needed — Next.js static export ships per-route HTML files.

## Verifying the deploy

1. Open `app.gradata.ai` → should redirect to `/login`
2. Sign in / sign up → lands on `/dashboard`
3. Dashboard renders KPI strip, decay curve, graduation pipeline, rules,
   categories, meta-rules, activity, privacy, A/B proof, methodology link
4. Browser console shows `[sentry] initialized env=production release=...`
   (or `[sentry] disabled: ...` if DSN not set — prod-safe)
5. Open Sentry dashboard, trigger a React error, confirm event arrives
6. `curl -I https://app.gradata.ai/` → response includes `strict-transport-security`,
   `content-security-policy`, `x-frame-options: DENY`
7. `curl -I https://app.gradata.ai/_next/static/...` → `cache-control: public, max-age=31536000, immutable`

## Local development

```bash
cd cloud/dashboard
pnpm install
cp .env.example .env.local      # fill in Supabase/API URL
pnpm dev                         # http://localhost:3000
```

## Local production build (verify before pushing)

```bash
cd cloud/dashboard
pnpm install --frozen-lockfile
pnpm build                       # produces out/
ls out/_headers out/_redirects   # confirm Pages config copied
```

## Notes on static export

- Dynamic routes like `/brains/[id]` work as client-side rendered (data
  fetched after hydration). No server-side generation needed.
- Sentry server/edge configs are stubbed — static export has no runtime
  for them.
- Fonts load via Google CSS (`<link>` in root layout) rather than
  `next/font/google`. Turbopack's font resolver conflicts with static
  export in Next 16.2; CSS `@import` is the stable path.
