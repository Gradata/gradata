import { GlassCard } from '@/components/layout/GlassCard'
import type { GraduationCounts } from '@/lib/analytics-client'

/**
 * 3-tier graduation visualization: INSTINCT (0.40) → PATTERN (0.60) → RULE (0.90).
 * Per SIM_A consensus: "the graduation pipeline IS the product."
 * No expert proposed this in blind validation (S103 cross-validation) — novel moat.
 */
export function GraduationProgressBar({ counts }: { counts: GraduationCounts }) {
  const total = counts.instinct + counts.pattern + counts.rule
  const tiers = [
    { key: 'INSTINCT' as const, count: counts.instinct, threshold: 0.40, color: '#3A82FF' },
    { key: 'PATTERN'  as const, count: counts.pattern,  threshold: 0.60, color: '#7C3AED' },
    { key: 'RULE'     as const, count: counts.rule,     threshold: 0.90, color: '#22C55E' },
  ]

  return (
    <GlassCard gradTop>
      <div className="mb-4 flex items-baseline justify-between">
        <h3 className="text-[15px] font-semibold">Graduation Pipeline</h3>
        <span className="text-[12px] text-[var(--color-body)]">{total} lessons total</span>
      </div>

      <div className="mb-5 flex h-2.5 w-full overflow-hidden rounded-full bg-white/[0.04]">
        {tiers.map((t) => {
          const pct = total === 0 ? 0 : (t.count / total) * 100
          return (
            <div
              key={t.key}
              className="h-full transition-all"
              style={{ width: `${pct}%`, background: t.color }}
              aria-label={`${t.key}: ${pct.toFixed(0)}%`}
            />
          )
        })}
      </div>

      <div className="grid grid-cols-3 gap-3">
        {tiers.map((t) => (
          <div key={t.key} className="rounded-[0.5rem] border border-[var(--color-border)] bg-white/[0.02] p-3">
            <div className="mb-1 flex items-center gap-2">
              <span className="h-2 w-2 rounded-full" style={{ background: t.color }} aria-hidden />
              <span className="font-mono text-[10px] uppercase tracking-wider text-[var(--color-body)]">
                {t.key}
              </span>
            </div>
            <div className="font-[var(--font-heading)] text-[24px] font-bold tabular-nums">
              {t.count}
            </div>
            <div className="mt-0.5 font-mono text-[10px] text-[var(--color-body)]">
              threshold {t.threshold.toFixed(2)} · avg conf {counts.avgConfidenceByState[t.key].toFixed(2)}
            </div>
          </div>
        ))}
      </div>
    </GlassCard>
  )
}
