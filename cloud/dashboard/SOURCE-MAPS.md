# Source maps → Sentry

Production stack traces are minified gibberish (`a.b.c` at line 1) without source maps. This doc covers the setup that makes them readable.

## Why

When the dashboard throws in prod, Sentry captures a stack trace against the minified JS bundle. Without source maps, frames look like:

```
at p (/assets/index-a8f2c91.js:1:12834)
```

With source maps uploaded, Sentry maps that back to:

```
at loadBrain (src/pages/BrainDetail.tsx:42:12)
```

The Vite Sentry plugin (`@sentry/vite-plugin`, already wired in `vite.config.ts`) generates `.map` files during build, uploads them to Sentry tagged with the release, then deletes them from the `dist/` output so they're never served to browsers.

## How it runs

Every push to `main` that touches `cloud/dashboard/**` triggers `.github/workflows/dashboard-source-maps.yml`:

1. Checkout, install pnpm 10 + Node 20
2. `pnpm install --frozen-lockfile`
3. `pnpm build` with `SENTRY_AUTH_TOKEN` set → Vite builds, plugin uploads + deletes maps
4. `wrangler pages deploy dist` → pushes the built output to Cloudflare Pages

This replaces the Cloudflare-native git-builder, which fails because it isn't configured to build from the `cloud/dashboard/` subpath.

## Required GitHub Actions secrets

Configure under repo → Settings → Secrets and variables → Actions:

| Secret | Value / where to get it |
|---|---|
| `SENTRY_AUTH_TOKEN` | Sentry → User settings → Auth tokens → **Create new token**. Scopes: `project:write` + `project:releases`. Copy once; Sentry won't show it again. |
| `SENTRY_ORG` | `gradata` |
| `SENTRY_PROJECT` | `gradata-dashboard` |
| `CLOUDFLARE_API_TOKEN` | Cloudflare → My Profile → API Tokens → **Create Token**. Template: "Custom". Permission: `Account → Cloudflare Pages → Edit`. Account Resources: include your account. |
| `CLOUDFLARE_ACCOUNT_ID` | `d568e4421afe0100d09df9e4d29bef81` |

All five must be set or the workflow will fail at either the build or deploy step.

## Verifying a deploy uploaded maps

1. Watch the workflow run in GitHub → Actions → Dashboard Build + Deploy
2. The "Build with Sentry source-map upload" step log should contain lines like `Successfully uploaded 12 source maps` and `Successfully created release gradata-dashboard@<sha>`
3. Open the dashboard, open DevTools, throw an error (easiest: paste `throw new Error('test')` in the console on a page that has a React error boundary, or comment out a required prop on a dev branch)
4. In Sentry → gradata-dashboard → Issues, open the new event. The stack trace should show **original file paths** (e.g. `src/pages/X.tsx`) not bundled asset names. If frames still show `/assets/index-<hash>.js`, the upload didn't run or the release tag doesn't match

If you see "Source map was not found" in Sentry, check the release name on the event matches the release the maps were uploaded under — both should be `gradata-dashboard@<full-commit-sha>`.

## Skipping the workflow

Include `[skip ci]` in the commit message:

```bash
git commit -m "docs: tweak wording [skip ci]"
```

The workflow's `if:` guard drops the job. Use this for pure-docs changes inside `cloud/dashboard/` that shouldn't trigger a redeploy.

## Manual trigger

Workflow has `workflow_dispatch:` — go to Actions → Dashboard Build + Deploy → **Run workflow** to trigger a build off `main` without pushing a commit. Useful after rotating secrets.

## Local dry-run

To verify the build path works without touching real credentials:

```bash
cd cloud/dashboard
SENTRY_AUTH_TOKEN=dummy SENTRY_ORG=gradata SENTRY_PROJECT=gradata-dashboard pnpm build
```

The Sentry plugin will fail to upload (expected — dummy token) but the build itself should succeed. This confirms the plugin is wired correctly and only the auth is missing.
