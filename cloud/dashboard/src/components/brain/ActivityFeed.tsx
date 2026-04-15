'use client'

import { useMemo } from 'react'
import { GlassCard } from '@/components/layout/GlassCard'
import { useApi } from '@/hooks/useApi'
import type { Brain } from '@/types/api'
import { mockActivity, type ActivityKind as LegacyActivityKind } from '@/lib/fixtures/mock-activity'

/**
 * Chronological learning-event feed. Consumes /brains/{id}/activity which
 * returns events filtered to visible kinds (graduation, self-healing,
 * recurrence, meta-rule-emerged, convergence, alert). Falls back to
 * fixtures when the brain has no events yet (cold start).
 *
 * Also accepts an optional `events` prop using outcome-first kinds
 * (rule.graduated / rule.patched / rule.recurrence / rule.mastered /
 * category.spike / meta_rule.emerged). When `events` is supplied,
 * the component renders it directly with the outcome-first label map
 * and demotes meta_rule.emerged events (not shown to humans).
 */

// ---------------------------------------------------------------------------
// Outcome-first event shape (new, for props-driven usage)
// ---------------------------------------------------------------------------

export type OutcomeActivityKind =
  | 'rule.graduated'
  | 'rule.patched'
  | 'rule.recurrence'
  | 'rule.mastered'
  | 'category.spike'
  | 'meta_rule.emerged'

export interface OutcomeActivityEvent {
  id: string
  kind: OutcomeActivityKind
  description: string
  at: string
}

type RenderableOutcomeKind = Exclude<OutcomeActivityKind, 'meta_rule.emerged'>

const LABELS: Record<RenderableOutcomeKind, { icon: string; label: string }> = {
  'rule.graduated': { icon: '✅', label: 'Rule graduated' },
  'rule.patched': { icon: '🔧', label: 'Rule updated' },
  'rule.recurrence': { icon: '⚠️', label: 'Slipped back' },
  'rule.mastered': { icon: '👥', label: 'Your team now gets this automatically' },
  'category.spike': { icon: '📈', label: 'More fixes this week' },
}

const EMPTY_COPY = 'Nothing to report this week. Your AI has been quiet — that is a good sign.'

export function renderableEvents<T extends { kind: OutcomeActivityKind }>(events: T[]): T[] {
  return events.filter((e) => e.kind !== 'meta_rule.emerged')
}

// ---------------------------------------------------------------------------
// Legacy API-driven shape (preserved)
// ---------------------------------------------------------------------------

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
  kind: LegacyActivityKind
  title: string
  detail: string
  created_at: string
}

const DOT: Record<LegacyActivityKind, string> = {
  graduation:     'bg-[var(--color-success)]',
  'self-healing': 'bg-[var(--color-accent-violet)]',
  recurrence:     'bg-[var(--color-warning)]',
  'meta-rule':    'bg-[var(--color-accent-blue)]',
  convergence:    'bg-[var(--color-accent-blue)]',
  alert:          'bg-[var(--color-destructive)]',
}

const KIND_TITLE: Record<LegacyActivityKind, string> = {
  graduation:     'Rule graduated',
  'self-healing': 'Self-healing patch applied',
  recurrence:     'Recurrence detected',
  'meta-rule':    'Meta-rule emerged',
  convergence:    'Convergence signal',
  alert:          'Alert',
}

function normalizeKind(apiType: string): LegacyActivityKind | null {
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

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export interface ActivityFeedProps {
  /**
   * Optional outcome-first event list. When provided, drives rendering
   * directly (meta_rule.emerged is demoted and not shown). When omitted,
   * the component falls back to the legacy API fetch behavior.
   */
  events?: OutcomeActivityEvent[]
}

export function ActivityFeed({ events }: ActivityFeedProps = {}) {
  // Always call hooks unconditionally (rules of hooks). When `events` is
  // provided, the legacy fetch result is simply ignored.
  const { data: brains } = useApi<Brain[]>('/brains')
  const primaryId = brains?.[0]?.id ?? null
  const { data: real } = useApi<ApiEvent[]>(
    primaryId ? `/brains/${primaryId}/activity` : null,
  )

  const legacyItems = useMemo<DisplayActivity[]>(() => {
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

  // --- Prop-driven outcome mode ---
  if (events !== undefined) {
    const rendered = renderableEvents(events)
    return (
      <GlassCard gradTop>
        <div className="mb-5 flex items-baseline justify-between">
          <h3 className="text-[15px] font-semibold">Recent Activity</h3>
          <span className="text-[12px] text-[var(--color-body)]">last 7 days</span>
        </div>
        {rendered.length === 0 ? (
          <p className="text-[13px] text-[var(--color-body)]">{EMPTY_COPY}</p>
        ) : (
          <ul className="space-y-3">
            {rendered.slice(0, 8).map((e) => {
              const meta = LABELS[e.kind as RenderableOutcomeKind]
              return (
                <li key={e.id} className="flex items-start gap-3 text-[13px]">
                  <span className="mt-0.5 w-5 text-center" aria-hidden>
                    {meta.icon}
                  </span>
                  <div className="flex-1">
                    <div>
                      {meta.label}{' '}
                      <span className="text-[var(--color-body)]">· {e.description}</span>
                    </div>
                    <div className="mt-0.5 font-mono text-[10px] text-[var(--color-body)]">
                      {ago(e.at)}
                    </div>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </GlassCard>
    )
  }

  // --- Legacy API-driven mode (preserved) ---
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
        {legacyItems.slice(0, 8).map((a) => (
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
