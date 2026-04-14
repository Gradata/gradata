'use client'

import { useEffect } from 'react'
import * as Sentry from '@sentry/nextjs'
import { GlassCard } from '@/components/layout/GlassCard'

/**
 * Top-level error boundary — caught client errors land here. Sentry already
 * captures the underlying exception via the SDK init; we just give the user
 * a survivable UI instead of a white screen.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    Sentry.captureException(error)
  }, [error])

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <GlassCard gradTop className="w-full max-w-md text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--color-destructive)]/20 ring-1 ring-[var(--color-destructive)]/40">
          <span className="font-mono text-[20px] text-[var(--color-destructive)]">!</span>
        </div>
        <h1 className="mb-2 text-[20px]">Something broke</h1>
        <p className="mb-1 text-[13px] text-[var(--color-body)]">
          The error has been logged. Try the action again, or head back to your dashboard.
        </p>
        {error.digest && (
          <p className="mb-6 font-mono text-[10px] text-[var(--color-body)]">
            id: {error.digest}
          </p>
        )}
        <div className="flex flex-col gap-2 sm:flex-row sm:justify-center">
          <button
            onClick={reset}
            className="rounded-[0.5rem] bg-gradient-brand px-4 py-2 text-[13px] font-medium text-white transition-all hover:opacity-90"
          >
            Try again
          </button>
          <a
            href="/dashboard"
            className="rounded-[0.5rem] border border-[var(--color-border)] px-4 py-2 text-[13px] text-[var(--color-body)] transition-all hover:border-[var(--color-border-hover)] hover:text-[var(--color-text)]"
          >
            Go to Overview
          </a>
        </div>
      </GlassCard>
    </div>
  )
}
