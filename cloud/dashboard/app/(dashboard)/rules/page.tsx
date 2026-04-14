'use client'

import { useMemo, useState } from 'react'
import { GlassCard } from '@/components/layout/GlassCard'
import { useApi } from '@/hooks/useApi'
import type { Brain, Lesson, PaginatedResponse } from '@/types/api'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { EmptyState } from '@/components/shared/EmptyState'

const STATE_STYLE: Record<Lesson['state'], string> = {
  INSTINCT: 'bg-[rgba(58,130,255,0.12)] text-[var(--color-accent-blue)]',
  PATTERN:  'bg-[rgba(124,58,237,0.12)] text-[var(--color-accent-violet)]',
  RULE:     'bg-[rgba(34,197,94,0.12)] text-[var(--color-success)]',
}

export default function RulesPage() {
  const [filter, setFilter] = useState<'all' | Lesson['state']>('all')
  const { data: brains, loading: loadingBrains } = useApi<Brain[]>('/brains')
  const primaryId = brains?.[0]?.id ?? null
  const { data: resp, loading } = useApi<PaginatedResponse<Lesson> | Lesson[]>(
    primaryId ? `/brains/${primaryId}/lessons` : null,
  )

  const lessons = useMemo<Lesson[]>(() => {
    if (!resp) return []
    return Array.isArray(resp) ? resp : resp.data
  }, [resp])

  const filtered = (filter === 'all' ? lessons : lessons.filter((l) => l.state === filter))
    .sort((a, b) => (b.confidence ?? 0) - (a.confidence ?? 0))

  if (loadingBrains || loading) return <LoadingSpinner className="py-20" />
  if (!primaryId) return <EmptyState title="No brain yet" description="Install the SDK to start graduating rules." />

  const states: Array<'all' | Lesson['state']> = ['all', 'INSTINCT', 'PATTERN', 'RULE']

  return (
    <>
      <header className="mb-7 flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h1 className="text-[22px]">Latest Rules</h1>
          <p className="mt-1 text-[13px] text-[var(--color-body)]">
            Every lesson · ranked by confidence · <span className="font-mono">{filtered.length}</span> shown
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {states.map((s) => (
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
              {s === 'all' ? 'all' : s.toLowerCase()}
            </button>
          ))}
        </div>
      </header>

      {filtered.length === 0 ? (
        <EmptyState title="No rules" description="Keep correcting and patterns will emerge." />
      ) : (
        <GlassCard gradTop>
          <ul className="divide-y divide-[var(--color-border)]">
            {filtered.slice(0, 100).map((l) => (
              <li key={l.id} className="py-3 first:pt-0 last:pb-0">
                <div className="mb-1 flex items-baseline gap-2.5 flex-wrap">
                  <span className={`rounded-[0.25rem] px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wider ${STATE_STYLE[l.state]}`}>
                    {l.state}
                  </span>
                  <span className="font-mono text-[10px] text-[var(--color-body)]">
                    {l.category}
                  </span>
                  <span className="font-mono text-[10px] text-[var(--color-body)]">
                    fired {l.fire_count ?? 0}×
                  </span>
                  <span className="ml-auto font-mono text-[10px] text-[var(--color-body)]">
                    {new Date(l.created_at).toLocaleDateString()}
                  </span>
                </div>
                <p className="text-[13px]">{l.description}</p>
              </li>
            ))}
          </ul>
        </GlassCard>
      )}
    </>
  )
}
