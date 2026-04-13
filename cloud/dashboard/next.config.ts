import type { NextConfig } from 'next'
import { withSentryConfig } from '@sentry/nextjs'

const nextConfig: NextConfig = {
  // Cloudflare Pages deploy: static export, no Node runtime at edge
  output: 'export',
  trailingSlash: false,
  images: { unoptimized: true },
  typescript: { ignoreBuildErrors: false },
  eslint: { ignoreDuringBuilds: false },
}

export default withSentryConfig(nextConfig, {
  org: process.env.SENTRY_ORG ?? 'gradata',
  project: process.env.SENTRY_PROJECT ?? 'gradata-dashboard',
  silent: !process.env.CI,
  disableLogger: true,
  // Skip source-map upload when auth token isn't present (dev-safe)
  authToken: process.env.SENTRY_AUTH_TOKEN,
  widenClientFileUpload: false,
  hideSourceMaps: true,
})
