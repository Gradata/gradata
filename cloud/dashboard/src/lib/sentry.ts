/**
 * Sentry error tracking for the dashboard.
 *
 * Safe to call with empty DSN — becomes a no-op. Logs init status
 * so misconfiguration is visible in browser console (don't fail silently).
 *
 * Privacy defaults:
 * - replay masks all text and blocks all media (paying users' brain data is sensitive)
 * - replaysSessionSampleRate: 0.0 (only record on error)
 * - replaysOnErrorSampleRate: 0.5 (cost guard against error storms)
 * - beforeSend strips Supabase tokens from URLs + auth headers
 */
import * as Sentry from '@sentry/react'

// Env vars read at BUILD time by Vite — requires rebuild on change in Cloudflare Pages
const DSN = import.meta.env.VITE_SENTRY_DSN as string | undefined
const ENV = (import.meta.env.VITE_SENTRY_ENVIRONMENT as string | undefined) ?? import.meta.env.MODE
const RELEASE = (import.meta.env.VITE_SENTRY_RELEASE as string | undefined) ?? 'gradata-dashboard@dev'

const SENSITIVE_PARAMS = ['access_token', 'refresh_token', 'token', 'api_key']

function scrubUrl(url: string): string {
  try {
    const u = new URL(url)
    let changed = false
    for (const param of SENSITIVE_PARAMS) {
      if (u.searchParams.has(param)) {
        u.searchParams.set(param, '[Filtered]')
        changed = true
      }
    }
    // Supabase puts tokens in URL hash (#access_token=...)
    if (u.hash && SENSITIVE_PARAMS.some((p) => u.hash.includes(`${p}=`))) {
      u.hash = '#[Filtered]'
      changed = true
    }
    return changed ? u.toString() : url
  } catch {
    return url
  }
}

export function initSentry(): void {
  if (!DSN) {
    // eslint-disable-next-line no-console
    console.info('[sentry] disabled: VITE_SENTRY_DSN not set')
    return
  }

  Sentry.init({
    dsn: DSN,
    environment: ENV,
    release: RELEASE,
    integrations: [
      Sentry.browserTracingIntegration(),
      Sentry.replayIntegration({
        maskAllText: true,
        blockAllMedia: true,
      }),
    ],
    tracesSampleRate: 0.1,
    replaysSessionSampleRate: 0.0,
    replaysOnErrorSampleRate: 0.5,
    sendDefaultPii: false,
    beforeSend(event) {
      // Scrub sensitive URL params from request context
      if (event.request?.url) {
        event.request.url = scrubUrl(event.request.url)
      }
      // Scrub any auth header that slipped through
      if (event.request?.headers) {
        const headers = event.request.headers as Record<string, string>
        for (const key of Object.keys(headers)) {
          const lower = key.toLowerCase()
          if (lower === 'authorization' || lower === 'cookie' || lower === 'x-api-key') {
            headers[key] = '[Filtered]'
          }
        }
      }
      // Scrub breadcrumb URLs (XHR/fetch breadcrumbs can contain tokens)
      if (event.breadcrumbs) {
        for (const crumb of event.breadcrumbs) {
          if (crumb.data && typeof crumb.data.url === 'string') {
            crumb.data.url = scrubUrl(crumb.data.url)
          }
        }
      }
      return event
    },
  })

  // eslint-disable-next-line no-console
  console.info(`[sentry] initialized env=${ENV} release=${RELEASE}`)
}
