import Link from 'next/link'
import type { Metadata } from 'next'
import { GlassCard } from '@/components/layout/GlassCard'

export const metadata: Metadata = {
  title: 'Not found — Gradata',
}

export default function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <GlassCard gradTop className="w-full max-w-md text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-brand shadow-[0_0_24px_rgba(58,130,255,0.4)]">
          <span className="font-mono text-[18px] font-bold text-white">404</span>
        </div>
        <h1 className="mb-2 text-[20px]">Not found</h1>
        <p className="mb-6 text-[13px] text-[var(--color-body)]">
          That route doesn&apos;t exist — or maybe it moved. Head back to your dashboard.
        </p>
        <div className="flex flex-col gap-2 sm:flex-row sm:justify-center">
          <Link
            href="/dashboard"
            className="rounded-[0.5rem] bg-gradient-brand px-4 py-2 text-[13px] font-medium text-white transition-all hover:opacity-90"
          >
            Go to Overview
          </Link>
          <Link
            href="/login"
            className="rounded-[0.5rem] border border-[var(--color-border)] px-4 py-2 text-[13px] text-[var(--color-body)] transition-all hover:border-[var(--color-border-hover)] hover:text-[var(--color-text)]"
          >
            Sign in
          </Link>
        </div>
      </GlassCard>
    </div>
  )
}
