// Minimal instrumentation — @sentry/nextjs expects this file to exist alongside sentry.*.config.ts.
// Static export has no server runtime so nothing to init here.
export async function register() {
  // no-op for static export
}
