'use client'

import { useMemo } from 'react'
import { PrivacyPosturePanel } from '@/components/brain/PrivacyPosturePanel'
import { GlassCard } from '@/components/layout/GlassCard'
import { useApi } from '@/hooks/useApi'
import type { Brain, BrainAnalytics } from '@/types/api'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { EmptyState } from '@/components/shared/EmptyState'

export default function PrivacyPage() {
  const { data: brains, loading: loadingBrains } = useApi<Brain[]>('/brains')
  const primaryId = brains?.[0]?.id ?? null
  const { data: analytics } = useApi<BrainAnalytics>(primaryId ? `/brains/${primaryId}/analytics` : null)

  const footprintKb = useMemo(() => {
    if (!analytics) return 0
    return Math.round((analytics.total_corrections ?? 0) * 11)
  }, [analytics])

  if (loadingBrains) return <LoadingSpinner className="py-20" />
  if (!primaryId) return <EmptyState title="No brain yet" description="Install the SDK first." />

  return (
    <>
      <header className="mb-7">
        <h1 className="text-[22px]">Privacy</h1>
        <p className="mt-1 text-[13px] text-[var(--color-body)]">
          What stays local, what reaches cloud, and the guarantees we make
        </p>
      </header>

      <div className="mb-4">
        <PrivacyPosturePanel footprintKb={footprintKb} />
      </div>

      <GlassCard gradTop>
        <h3 className="mb-4 text-[15px] font-semibold">What reaches the cloud</h3>
        <ul className="space-y-3 text-[13px]">
          <Row
            label="Synthesized principles"
            detail="The distilled rule text after correction events have graduated. No raw correction bodies."
            tone="pos"
          />
          <Row
            label="Aggregate counters"
            detail="Correction counts, graduation counters, fire counts — numbers, not content."
            tone="pos"
          />
          <Row
            label="Session metadata"
            detail="Timestamps and session IDs so the graduation engine can reason about recency."
            tone="neu"
          />
          <Row
            label="Raw correction text"
            detail="Never. Correction bodies stay in your local brain file."
            tone="neg-good"
          />
          <Row
            label="Draft / final content"
            detail="Never. The SDK redacts draft and final previews before upload."
            tone="neg-good"
          />
        </ul>

        <p className="mt-6 font-mono text-[11px] text-[var(--color-body)]">
          Per SIM_A §5A: the correction store is an &quot;unprecedentedly valuable attack surface&quot;
          — keeping it local is architectural, not a setting.
        </p>
      </GlassCard>
    </>
  )
}

function Row({ label, detail, tone }: {
  label: string; detail: string; tone: 'pos' | 'neu' | 'neg-good'
}) {
  const dot =
    tone === 'pos'      ? 'bg-[var(--color-accent-blue)]'
    : tone === 'neg-good' ? 'bg-[var(--color-success)]'
    :                      'bg-[var(--color-body)]'
  const prefix =
    tone === 'pos'      ? 'sent'
    : tone === 'neg-good' ? 'never sent'
    :                      'metadata'
  return (
    <li className="flex items-start gap-3 rounded-[0.5rem] border border-[var(--color-border)] bg-white/[0.02] p-3">
      <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${dot}`} aria-hidden />
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2">
          <span className="font-medium">{label}</span>
          <span className="font-mono text-[10px] uppercase tracking-wider text-[var(--color-body)]">{prefix}</span>
        </div>
        <div className="mt-0.5 text-[12px] text-[var(--color-body)]">{detail}</div>
      </div>
    </li>
  )
}
