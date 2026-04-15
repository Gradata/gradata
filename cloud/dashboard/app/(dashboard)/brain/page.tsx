'use client'

import { Suspense, useMemo } from 'react'
import { useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { useApi } from '@/hooks/useApi'
import type { Brain, BrainAnalytics, Correction, Lesson, PaginatedResponse } from '@/types/api'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { ErrorState } from '@/components/shared/ErrorState'
import { GlassCard } from '@/components/layout/GlassCard'
import { KpiStrip } from '@/components/brain/KpiStrip'
import { GraduationProgressBar } from '@/components/brain/GraduationProgressBar'
import { ActiveRulesPanel } from '@/components/brain/ActiveRulesPanel'
import { CategoriesChart } from '@/components/brain/CategoriesChart'
import { ClearDemoButton } from '@/components/brain/ClearDemoButton'
import { computeKpis, computeGraduationCounts } from '@/lib/analytics-client'

export default function BrainDetailPage() {
  return (
    <Suspense fallback={<LoadingSpinner className="py-20" />}>
      <BrainDetail />
    </Suspense>
  )
}

function BrainDetail() {
  const params = useSearchParams()
  const id = params.get('id')

  const { data: brain, loading, error, refetch } = useApi<Brain>(id ? `/brains/${id}` : null)
  const { data: analytics } = useApi<BrainAnalytics>(id ? `/brains/${id}/analytics` : null)
  const { data: correctionsResp } = useApi<PaginatedResponse<Correction> | Correction[]>(
    id ? `/brains/${id}/corrections` : null,
  )
  const { data: lessonsResp } = useApi<PaginatedResponse<Lesson> | Lesson[]>(
    id ? `/brains/${id}/lessons` : null,
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

  if (!id) return <ErrorState message="Missing brain ID. Navigate from the Overview page." />
  if (loading) return <LoadingSpinner className="py-20" />
  if (error) return <ErrorState message={error} onRetry={refetch} />
  if (!brain) return <ErrorState message="Brain not found" />

  return (
    <>
      <header className="mb-7">
        <Link href="/dashboard" className="mb-3 inline-block font-mono text-[11px] text-[var(--color-body)] hover:text-[var(--color-accent-blue)]">
          ← back to overview
        </Link>
        <h1 className="text-[22px]">{brain.name}</h1>
        <p className="mt-1 text-[13px] text-[var(--color-body)]">
          {brain.domain} · {brain.lesson_count} lessons · {brain.correction_count} corrections
          {brain.last_sync && ` · last synced ${new Date(brain.last_sync).toLocaleString()}`}
        </p>
      </header>

      {kpis && <KpiStrip metrics={kpis} />}

      <div className="mb-4">
        <GraduationProgressBar counts={gradCounts} />
      </div>

      <div className="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ActiveRulesPanel lessons={lessons} />
        {analytics && <CategoriesChart analytics={analytics} />}
      </div>

      <GlassCard gradTop>
        <h3 className="mb-4 text-[15px] font-semibold">Brain details</h3>
        <dl className="grid grid-cols-1 gap-3 text-[13px] sm:grid-cols-2">
          <Row label="Brain ID" value={brain.id} mono />
          <Row label="Created" value={new Date(brain.created_at).toLocaleString()} />
          <Row label="User ID" value={brain.user_id} mono />
          <Row label="Domain" value={brain.domain} />
        </dl>
      </GlassCard>

      <GlassCard gradTop className="mt-4">
        <h3 className="mb-2 text-[15px] font-semibold">Demo data</h3>
        <p className="mb-4 text-[12px] text-[var(--color-body)]">
          New accounts get a seeded demo brain so the dashboard has something to show on day one.
          Remove it once you&apos;ve connected your own brain.
        </p>
        <ClearDemoButton brainId={brain.id} onCleared={refetch} />
      </GlassCard>
    </>
  )
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt className="font-mono text-[10px] uppercase tracking-wider text-[var(--color-body)]">{label}</dt>
      <dd className={mono ? 'font-mono text-[11px] break-all' : ''}>{value}</dd>
    </div>
  )
}
