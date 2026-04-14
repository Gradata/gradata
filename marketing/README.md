# gradata.ai — Marketing Site

Next.js 16 App Router, static export. Replaces the legacy Vite SPA at `.tmp/website/`.

## Why Next.js

The previous Vite SPA served blank HTML to Googlebot and AEO crawlers, killing organic
discovery. This site pre-renders every route to real HTML at build time — SEO content
lives in the markup, not in a JS bundle.

## Develop

```bash
cd marketing
pnpm install
pnpm dev
# http://localhost:3000
```

## Build

```bash
pnpm build
# static HTML lands in out/
ls out/
```

## Deploy (Cloudflare Pages)

```bash
pnpm build
wrangler pages deploy out --project-name=gradata-website
```

The Pages project is `gradata-website` (custom domain `gradata.ai`).

## Structure

```
marketing/
├─ app/
│  ├─ layout.tsx          # Root layout: V3 theme, fonts, JSON-LD, noise overlay
│  ├─ page.tsx            # Home — hero + KPI proof row + CTA
│  ├─ how-it-works/       # Graduation pipeline explainer
│  ├─ pricing/            # 4 plan cards
│  ├─ docs/               # Quickstart + link to GitHub docs
│  ├─ legal/privacy/
│  ├─ legal/terms/
│  ├─ sitemap.ts          # Generates /sitemap.xml
│  ├─ robots.ts           # Generates /robots.txt
│  └─ globals.css
├─ src/
│  ├─ components/         # Header, Footer, Hero, GlassCard, NoiseOverlay, etc.
│  └─ lib/                # site metadata + cn util
├─ public/
│  ├─ _headers            # Cloudflare Pages security headers
│  ├─ _redirects          # www → apex, /login → app.gradata.ai
│  └─ favicon.svg
├─ next.config.ts         # output: 'export', images unoptimized
└─ wrangler.toml
```

## SEO checklist

- [x] Per-route `metadata` exports (title, description, openGraph, twitter, canonical)
- [x] JSON-LD `Organization` schema in root layout
- [x] `sitemap.ts` auto-generates `/sitemap.xml`
- [x] `robots.ts` auto-generates `/robots.txt` with sitemap reference
- [x] All HTML pre-rendered — content visible to crawlers without JS execution
