# Sentry Setup

Sentry is wired into the backend (FastAPI on Railway) and the dashboard (Vite+React on Cloudflare Pages). Both are **disabled by default** — they stay no-op until you set the DSN env vars.

## 1. Create Sentry projects

Go to https://sentry.io/ → create two projects under the `gradata` organization:

| Project slug | Platform | Used by |
|---|---|---|
| `gradata-cloud` | Python / FastAPI | Backend (Railway) |
| `gradata-dashboard` | Browser / React | Dashboard (Cloudflare Pages) |

Copy the DSN from each project's settings. Also create an **auth token** with `project:releases` + `project:write` scope for source-map uploads (one token covers both projects).

## 2. Set Railway env vars (backend)

In Railway → `gradata-production` service → Variables:

```
GRADATA_SENTRY_DSN=https://...@o0.ingest.sentry.io/<project-id>
GRADATA_SENTRY_TRACES_SAMPLE_RATE=0.1   # optional, defaults to 0.1
GRADATA_ENVIRONMENT=production          # already set
```

Railway auto-deploys on env change. Check logs for the init line:

```
INFO:app.sentry_init:Sentry initialized: environment=production release=gradata-cloud@<sha> traces_sample_rate=0.10
```

If you see `Sentry disabled: GRADATA_SENTRY_DSN not set`, the env var didn't load.

## 3. Set Cloudflare Pages env vars (dashboard)

In Cloudflare → Pages → `gradata-dashboard` → Settings → Environment variables (Production):

```
VITE_SENTRY_DSN=https://...@o0.ingest.sentry.io/<project-id>
VITE_SENTRY_ENVIRONMENT=production           # optional, defaults to MODE
VITE_SENTRY_RELEASE=gradata-dashboard@<ver>  # optional

# For source-map upload (makes prod stack traces readable)
SENTRY_AUTH_TOKEN=<token-from-step-1>
SENTRY_ORG=gradata
SENTRY_PROJECT=gradata-dashboard
```

**Important:** Vite reads `VITE_*` vars **at build time**. After setting them, trigger a rebuild (retry deploy, or push a commit). Reading env changes requires a new build.

Open the dashboard in a browser and check console for:

```
[sentry] initialized env=production release=gradata-dashboard@...
```

## 4. Verify events reach Sentry

**Backend:** Hit any route that raises (or intentionally trigger one). An event should appear in the `gradata-cloud` project within ~30s.

**Frontend:** In the dashboard, trigger a React render error (e.g. comment out a required prop on a temporary build). Replay will record only because an error fired.

If no events show up:
- Check the init log line exists (step 2/3).
- Check the Sentry project's **inbound rate** in Stats — rejected events indicate DSN mismatch.
- Check browser Network tab — Sentry POSTs to `ingest.sentry.io`. If blocked by adblock, enable a tunnel route (future work).

## 5. What's captured / what's not

**Captured:**
- Unhandled backend exceptions (FastAPI + Starlette integration)
- Frontend JS errors, unhandled promise rejections, React error boundaries
- 10% of transactions (backend) for perf monitoring
- Session replays, but only on error (to control cost), with all text masked

**NOT captured (by design):**
- Request bodies (Stripe webhooks contain customer email)
- Cookies, Authorization headers, X-API-Key, X-Stripe-Signature
- `supabase_service_key`, `stripe_webhook_secret`, `access_token`, `refresh_token` anywhere in extras/contexts
- IP addresses, usernames (`send_default_pii=False`)
- Local variables in stack frames (`include_local_variables=False`)

## 6. Adjusting volume later

If cost runs high:

- Drop `GRADATA_SENTRY_TRACES_SAMPLE_RATE` (backend) from `0.1` → `0.02`
- In `src/lib/sentry.ts` (frontend): drop `tracesSampleRate` and `replaysOnErrorSampleRate`
- Add server-side sampling rules in the Sentry project settings (filter out noisy errors)

## Files touched

- `cloud/pyproject.toml` — added `sentry-sdk[fastapi]>=2.18.0`
- `cloud/app/config.py` — `sentry_dsn`, `sentry_traces_sample_rate`, `sentry_release` fields
- `cloud/app/sentry_init.py` — init + PII scrubber
- `cloud/app/main.py` — calls `init_sentry(settings)` in `create_app()`
- `cloud/dashboard/package.json` — added `@sentry/react`, `@sentry/vite-plugin`
- `cloud/dashboard/src/lib/sentry.ts` — init + PII scrubber
- `cloud/dashboard/src/main.tsx` — calls `initSentry()` before `createRoot`
- `cloud/dashboard/vite.config.ts` — conditional source-map upload plugin
- `cloud/tests/test_sentry.py` — 11 tests covering init paths + scrubber
