import { GlassCard } from '@/components/layout/GlassCard'
import { mockActivity, type ActivityKind } from '@/lib/fixtures/mock-activity'

/**
 * Chronological learning-event feed. Kinds color-coded per mockup:
 * graduation (green), self-healing (violet), recurrence (amber),
 * meta-rule (blue), convergence (blue), alert (red).
 *
 * TODO(backend): fetch from /api/v1/brains/{id}/activity when endpoint ships.
 */
const DOT: Record<ActivityKind, string> = {
  graduation:    'bg-[var(--color-success)]',
  'self-healing': 'bg-[var(--color-accent-violet)]',
  recurrence:    'bg-[var(--color-warning)]',
  'meta-rule':   'bg-[var(--color-accent-blue)]',
  convergence:   'bg-[var(--color-accent-blue)]',
  alert:         'bg-[var(--color-destructive)]',
}

const ago = (iso: string): string => {
  const diffMs = Date.now() - new Date(iso).getTime()
  const h = Math.floor(diffMs / 3600_000)
  if (h < 1) return 'just now'
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

export function ActivityFeed() {
  return (
    <GlassCard gradTop>
      <div className="mb-5 flex items-baseline justify-between">
        <h3 className="text-[15px] font-semibold">Recent Activity</h3>
        <span className="text-[12px] text-[var(--color-body)]">last 7 days</span>
      </div>
      <ul className="space-y-3">
        {mockActivity.map((a) => (
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
