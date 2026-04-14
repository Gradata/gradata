import * as Sentry from '@sentry/nextjs'

const DSN = process.env.NEXT_PUBLIC_SENTRY_DSN

if (DSN) {
  Sentry.init({
    dsn: DSN,
    environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT ?? 'production',
    release: process.env.NEXT_PUBLIC_SENTRY_RELEASE ?? 'gradata-dashboard@dev',
    integrations: [
      Sentry.replayIntegration({ maskAllText: true, blockAllMedia: true }),
    ],
    tracesSampleRate: 0.1,
    replaysSessionSampleRate: 0.0,
    replaysOnErrorSampleRate: 0.5,
    sendDefaultPii: false,
    beforeSend(event) {
      if (event.request?.headers) {
        const h = event.request.headers as Record<string, string>
        for (const k of Object.keys(h)) {
          if (/^(authorization|cookie|x-api-key)$/i.test(k)) h[k] = '[Filtered]'
        }
      }
      if (event.request?.url) {
        try {
          const u = new URL(event.request.url)
          for (const p of ['access_token', 'refresh_token', 'token', 'api_key']) {
            if (u.searchParams.has(p)) u.searchParams.set(p, '[Filtered]')
          }
          if (u.hash && /access_token|token/.test(u.hash)) u.hash = '#[Filtered]'
          event.request.url = u.toString()
        } catch { /* non-URL, leave */ }
      }
      return event
    },
  })
} else if (typeof window !== 'undefined') {
  // eslint-disable-next-line no-console
  console.info('[sentry] disabled: NEXT_PUBLIC_SENTRY_DSN not set')
}
