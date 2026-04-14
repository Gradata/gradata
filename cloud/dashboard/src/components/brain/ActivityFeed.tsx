'use client'

import { useMemo } from 'react'
import { GlassCard } from '@/components/layout/GlassCard'
import { useApi } from '@/hooks/useApi'
import type { Brain } from '@/types/api'
import { mockActivity, type ActivityKind } from '@/lib/fixtures/mock-activity'

/**
 * Chronological learning-event feed. Consumes /brains/{id}/activity which
 * returns events filtered to visible kinds (graduation, self-healing,
 * recurrence, meta-rule-emerged, convergence, alert). Falls back to
 * fixtures when the brain has no events yet (cold start).
 */

interface ApiEvent {
  id: string
  brain_id: string
  type: string
  source: string
  data: Record<string, any>
  tags: string[]
  session: number | null
  created_at: string
}

interface DisplayActivity {
  id: string
  kind: ActivityKind
  title: string
  detail: string
  created_at: string
}

const DOT: Record<ActivityKind, string> = {
  graduation:     'bg-[var(--color-success)]',
  'self-healing': 'bg-[var(--color-accent-violet)]',
  recurrence:     'bg-[var(--color-warning)]',
  'meta-rule':    'bg-[var(--color-accent-blue)]',
  convergence:    'bg-[var(--color-accent-blue)]',
  alert:          'bg-[var(--color-destructive)]',
}

const KIND_TITLE: Record<ActivityKind, string> = {
  graduation:     'Rule graduated',
  'self-healing': 'Self-healing patch applied',
  recurrence:     'Recurrence detected',
  'meta-rule':    'Meta-rule emerged',
  convergence:    'Convergence signal',
  alert:          'Alert',
}

function normalizeKind(apiType: string): ActivityKind | null {
  switch (apiType) {
    case 'graduation':         return 'graduation'
    case 'self-healing':       return 'self-healing'
    case 'recurrence':         return 'recurrence'
    case 'meta-rule-emerged':  return 'meta-rule'
    case 'convergence':        return 'convergence'
    case 'alert':              return 'alert'
    default:                   return null
  }
}

function extractDetail(event: ApiEvent): string {
  const d = event.data ?? {}
  return d.title || d.description || d.lesson_description || d.message || event.source || '—'
}

const ago = (iso: string): string => {
  const diffMs = Date.now() - new Date(iso).getTime()
  const h = Math.floor(diffMs / 3600_000)
  if (h < 1) return 'just now'
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

export function ActivityFeed() {
  const { data: brains } = useApi<Brain[]>('/brains')
  const primaryId = brains?.[0]?.id ?? null
  const { data: real } = useApi<ApiEvent[]>(
    primaryId ? `/brains/${primaryId}/activity` : null,
  )

  const items = useMemo<DisplayActivity[]>(() => {
    if (real && real.length > 0) {
      return real
        .map((e) => {
          const kind = normalizeKind(e.type)
          if (!kind) return null
          return {
            id: e.id,
            kind,
            title: KIND_TITLE[kind],
            detail: extractDetail(e),
            created_at: e.created_at,
          }
        })
        .filter((x): x is DisplayActivity => x !== null)
    }
    // Fallback: demo data so the surface isn't empty
    return mockActivity.map((a) => ({
      id: a.id,
      kind: a.kind,
      title: a.title,
      detail: a.detail,
      created_at: a.created_at,
    }))
  }, [real])

  const showingDemo = !real || real.length === 0

  return (
    <GlassCard gradTop>
      <div className="mb-5 flex items-baseline justify-between">
        <h3 className="text-[15px] font-semibold">Recent Activity</h3>
        <span className="text-[12px] text-[var(--color-body)]">
          {showingDemo ? 'demo data — yours appear on first sync' : 'last 7 days'}
        </span>
      </div>
      <ul className="space-y-3">
        {items.slice(0, 8).map((a) => (
          <li key={a.id} className="flex items-start gap-3 text-[13px]">
            <span className={`mt-1.5 h-1.5 w-1.5 rounded-full ${DOT[a.kind]}`} aria-hidden />
            <div className="flex-1">
              <div>
                {a.title}{' '}
                <span className="text-[var(--color-body)]">· {a.detail}</span>
              </div>
              <div className="mt-0.5 font-mono text-[10px] text-[var(--color-body)]">
                {ago(a.created_at)}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </GlassCard>
  )
}
