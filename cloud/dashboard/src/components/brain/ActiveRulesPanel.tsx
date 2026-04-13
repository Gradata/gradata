import { GlassCard } from '@/components/layout/GlassCard'
import type { Lesson } from '@/types/api'

/**
 * Rule list per SIM103 (34/50) + WAVE2 §5: hide raw confidence text
 * (SIM16: 80% said "I don't audit these"). Surface implicit approval
 * count and recurrence indicator instead.
 *
 * TODO(backend): Bayesian alpha/beta confidence + zombie/suppression
 * flags require schema additions. Placeholders noted inline.
 */
export function ActiveRulesPanel({ lessons }: { lessons: Lesson[] }) {
  const rules = lessons
    .filter((l) => l.state === 'RULE' || l.state === 'PATTERN')
    .sort((a, b) => (b.confidence ?? 0) - (a.confidence ?? 0))
    .slice(0, 8)

  return (
    <GlassCard gradTop>
      <div className="mb-5 flex items-baseline justify-between">
        <h3 className="text-[15px] font-semibold">Active Rules</h3>
        <span className="text-[12px] text-[var(--color-body)]">top 8</span>
      </div>
      <ul className="space-y-3">
        {rules.length === 0 && (
          <li className="text-[13px] text-[var(--color-body)]">
            No graduated rules yet. Keep correcting and patterns will emerge.
          </li>
        )}
        {rules.map((rule) => {
          const fires = rule.fire_count ?? 0
          // Recurrence: if fires > 0, the rule has been invoked (implicit approval or misfire);
          // we surface that as "fired N×" vs "clean" until backend ships miss-count.
          const status: 'clean' | 'fired' =
            fires === 0 ? 'clean' : 'fired'
          const statusColor =
            status === 'clean'
              ? 'bg-[var(--color-success)]'
              : 'bg-[var(--color-accent-blue)]'
          return (
            <li key={rule.id} className="flex items-start gap-3">
              <span
                className={`mt-1.5 h-2 w-2 rounded-full ${statusColor}`}
                aria-hidden
              />
              <div className="flex-1 min-w-0">
                <div className="text-[13px]">{rule.description}</div>
                <div className="mt-0.5 flex flex-wrap gap-x-3 gap-y-0.5 font-mono text-[10px] text-[var(--color-body)]">
                  <span>{rule.category}</span>
                  <span className="uppercase">{rule.state}</span>
                  <span>
                    {status === 'clean' ? 'clean · no fires yet' : `fired ${fires}×`}
                  </span>
                </div>
              </div>
            </li>
          )
        })}
      </ul>
    </GlassCard>
  )
}
