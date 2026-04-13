'use client'

import { useMemo, useState } from 'react'
import { useApi } from '@/hooks/useApi'
import type { Brain, BrainAnalytics, Correction, Lesson, PaginatedResponse } from '@/types/api'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { EmptyState } from '@/components/shared/EmptyState'
import { computeKpis, computeGraduationCounts } from '@/lib/analytics-client'
import { KpiStrip } from '@/components/brain/KpiStrip'
import { GraduationProgressBar } from '@/components/brain/GraduationProgressBar'
import { CorrectionDecayCurve } from '@/components/brain/CorrectionDecayCurve'
import { ActiveRulesPanel } from '@/components/brain/ActiveRulesPanel'
import { CategoriesChart } from '@/components/brain/CategoriesChart'
import { MetaRulesGrid } from '@/components/brain/MetaRulesGrid'
import { ActivityFeed } from '@/components/brain/ActivityFeed'
import { PrivacyPosturePanel } from '@/components/brain/PrivacyPosturePanel'
import { ABProofPanel } from '@/components/brain/ABProofPanel'
import { MethodologyLink } from '@/components/brain/MethodologyLink'

export default function DashboardPage() {
  const [range, setRange] = useState<'7d' | '30d' | '90d'>('30d')

  const { data: brains, loading: loadingBrains } = useApi<Brain[]>('/brains')
  const primaryBrainId = brains?.[0]?.id ?? null

  const { data: analytics } = useApi<BrainAnalytics>(
    primaryBrainId ? `/brains/${primaryBrainId}/analytics` : null,
  )
  const { data: correctionsResp } = useApi<PaginatedResponse<Correction> | Correction[]>(
    primaryBrainId ? `/brains/${primaryBrainId}/corrections` : null,
  )
  const { data: lessonsResp } = useApi<PaginatedResponse<Lesson> | Lesson[]>(
    primaryBrainId ? `/brains/${primaryBrainId}/lessons` : null,
  )

  const corrections = useMemo<Correction[]>(() => {
    if (!correctionsResp) return []
    return Array.isArray(correctionsResp) ? correctionsResp : correctionsResp.data
  }, [correctionsResp])

  const lessons = useMemo<Lesson[]>(() => {
    if (!lessonsResp) return []
    return Array.isArray(lessonsResp) ? lessonsResp : lessonsResp.data
  }, [lessonsResp])

  const kpis = useMemo(
    () => (analytics ? computeKpis(analytics, corrections, lessons) : null),
    [analytics, corrections, lessons],
  )
  const gradCounts = useMemo(() => computeGraduationCounts(lessons), [lessons])

  if (loadingBrains) return <LoadingSpinner className="py-20" />

  if (!primaryBrainId) {
    return (
      <div className="py-12">
        <EmptyState
          title="AI that learns the corrections you keep making"
          description='Install the Gradata SDK and run your first session. Your brain stays local — the dashboard is a lens over it.'
        />
        <pre className="mx-auto mt-6 w-fit rounded-[0.5rem] border border-[var(--color-border)] bg-[rgba(21,29,48,0.6)] px-5 py-3 font-mono text-[13px] text-[var(--color-accent-blue)]">
          pip install gradata
        </pre>
        <p className="mt-6 text-center font-mono text-[12px] text-[var(--color-body)]">
          Mem0 remembers. Gradata learns.
        </p>
      </div>
    )
  }

  return (
    <>
      {/* Page header + time range pills */}
      <header className="mb-7 flex items-center justify-between">
        <div>
          <h1 className="text-[22px]">Overview</h1>
          <p className="mt-1 text-[13px] text-[var(--color-body)]">
            Your brain&apos;s learning progress
          </p>
        </div>
        <div className="flex gap-1.5">
          {(['7d', '30d', '90d'] as const).map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => setRange(r)}
              className={`rounded-[0.5rem] border px-3.5 py-1.5 text-[12px] font-medium transition-all ${
                r === range
                  ? 'border-[rgba(58,130,255,0.3)] bg-[rgba(58,130,255,0.12)] text-[var(--color-text)]'
                  : 'border-[var(--color-border)] bg-transparent text-[var(--color-body)] hover:border-[var(--color-border-hover)] hover:text-[var(--color-text)]'
              }`}
            >
              {r}
            </button>
          ))}
        </div>
      </header>

      {/* 4 KPI cards */}
      {kpis && <KpiStrip metrics={kpis} />}

      {/* Hero: correction decay curve */}
      <CorrectionDecayCurve corrections={corrections} range={range} />

      {/* Graduation pipeline (3-tier, sim-validated as the moat) */}
      <div className="mb-4">
        <GraduationProgressBar counts={gradCounts} />
      </div>

      {/* Rules + Categories */}
      <div className="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ActiveRulesPanel lessons={lessons} />
        {analytics && <CategoriesChart analytics={analytics} />}
      </div>

      {/* Meta rules + Activity */}
      <div className="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <MetaRulesGrid />
        <ActivityFeed />
      </div>

      {/* Trust surface: privacy + A/B proof */}
      <div className="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <PrivacyPosturePanel footprintKb={kpis?.footprintKb ?? 0} />
        <ABProofPanel />
      </div>

      <div className="text-center">
        <MethodologyLink />
      </div>
    </>
  )
}
