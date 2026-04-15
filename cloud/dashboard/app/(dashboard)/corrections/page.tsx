'use client'

import { useMemo, useState } from 'react'
import { GlassCard } from '@/components/layout/GlassCard'
import { useApi } from '@/hooks/useApi'
import type { Brain, Correction, PaginatedResponse } from '@/types/api'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { EmptyState } from '@/components/shared/EmptyState'

const SEVERITY_STYLE: Record<Correction['severity'], string> = {
  trivial:  'bg-white/[0.04] text-[var(--color-body)]',
  minor:    'bg-[rgba(58,130,255,0.12)] text-[var(--color-accent-blue)]',
  moderate: 'bg-[rgba(234,179,8,0.12)] text-[var(--color-warning)]',
  major:    'bg-[rgba(239,68,68,0.12)] text-[var(--color-destructive)]',
  rewrite:  'bg-[rgba(239,68,68,0.2)]  text-[var(--color-destructive)]',
}

export default function CorrectionsPage() {
  const [filter, setFilter] = useState<'all' | Correction['severity']>('all')
  const { data: brains, loading: loadingBrains } = useApi<Brain[]>('/brains')
  const primaryId = brains?.[0]?.id ?? null
  const { data: resp, loading } = useApi<PaginatedResponse<Correction> | Correction[]>(
    primaryId ? `/brains/${primaryId}/corrections` : null,
  )

  const corrections = useMemo<Correction[]>(() => {
    if (!resp) return []
    return Array.isArray(resp) ? resp : resp.data
  }, [resp])

  const filtered = filter === 'all' ? corrections : corrections.filter((c) => c.severity === filter)

  if (loadingBrains || loading) return <LoadingSpinner className="py-20" />
  if (!primaryId) return (
    <EmptyState
      title="No brain yet"
      description="Install the SDK and log your first correction to see it here. See Setup in the left nav for install instructions."
    />
  )

  const severities: Array<'all' | Correction['severity']> = ['all', 'trivial', 'minor', 'moderate', 'major', 'rewrite']

  return (
    <>
      <header className="mb-7 flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h1 className="text-[22px]">Corrections</h1>
          <p className="mt-1 text-[13px] text-[var(--color-body)]">
            Every correction, newest first · <span className="font-mono">{filtered.length}</span> shown
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {severities.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setFilter(s)}
              className={`rounded-[0.5rem] border px-3 py-1 text-[11px] font-medium transition-all ${
                s === filter
                  ? 'border-[rgba(58,130,255,0.3)] bg-[rgba(58,130,255,0.12)] text-[var(--color-text)]'
                  : 'border-[var(--color-border)] text-[var(--color-body)] hover:border-[var(--color-border-hover)]'
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </header>

      {filtered.length === 0 ? (
        <EmptyState title="No corrections" description={filter === 'all' ? 'Your first correction will appear here.' : `No corrections with severity: ${filter}`} />
      ) : (
        <GlassCard gradTop>
          <ul className="divide-y divide-[var(--color-border)]">
            {filtered.slice(0, 50).map((c) => (
              <li key={c.id} className="py-3 first:pt-0 last:pb-0">
                <div className="mb-1 flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
                  <span className={`rounded-[0.25rem] px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wider ${SEVERITY_STYLE[c.severity]}`}>
                    {c.severity}
                  </span>
                  <span className="font-mono text-[10px] text-[var(--color-body)]">
                    {c.category}
                  </span>
                  <span className="ml-auto font-mono text-[10px] text-[var(--color-body)]">
                    {new Date(c.created_at).toLocaleString()}
                  </span>
                </div>
                <p className="text-[13px]">{c.description}</p>
              </li>
            ))}
          </ul>
        </GlassCard>
      )}
    </>
  )
}
