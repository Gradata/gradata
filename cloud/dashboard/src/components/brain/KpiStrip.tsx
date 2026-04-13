import { GlassCard } from '@/components/layout/GlassCard'
import type { KpiMetrics } from '@/lib/analytics-client'

/**
 * 4 KPI cards above the fold. Sim-validated metric set (S103, WAVE2):
 * 1. Correction rate drop % (the only universally respected metric per S101)
 * 2. Sessions to graduation (target <3, with 95% CI — differentiator vs Mem0/Letta)
 * 3. 0 Misfires (trust signal from S103 ANALYSIS)
 * 4. Brain footprint (observability lens, not "cloud owns your data")
 */
export function KpiStrip({ metrics }: { metrics: KpiMetrics }) {
  const fmtDelta = (pct: number) =>
    pct === 0 ? '—' : `${pct > 0 ? '+' : ''}${pct.toFixed(0)}%`

  const items: Array<{
    label: string
    value: string
    change?: string
    changeTone?: 'pos' | 'neg' | 'neu'
  }> = [
    {
      label: 'Correction Rate',
      value: metrics.correctionRateDeltaPct === 0
        ? '—'
        : `${fmtDelta(metrics.correctionRateDeltaPct)}`,
      change: `${metrics.correctionsThisWeek} this week · ${metrics.correctionsPriorWeek} prior`,
      changeTone:
        metrics.correctionRateDeltaPct < 0 ? 'pos'
          : metrics.correctionRateDeltaPct > 0 ? 'neg'
            : 'neu',
    },
    {
      label: 'Sessions to Graduation',
      value: metrics.sessionsToGraduation === 0
        ? '—'
        : metrics.sessionsToGraduation.toFixed(1),
      change: metrics.sessionsToGraduation > 0
        ? `95% CI [${metrics.sessionsToGraduationLow}, ${metrics.sessionsToGraduationHigh}]`
        : 'awaiting first graduation',
      changeTone: 'neu',
    },
    {
      label: 'Misfires',
      value: metrics.misfireCount.toString(),
      change: `across ${metrics.totalFires} rule fires`,
      changeTone: metrics.misfireCount === 0 ? 'pos' : 'neg',
    },
    {
      label: 'Brain Footprint',
      value: metrics.footprintKb >= 1024
        ? `${(metrics.footprintKb / 1024).toFixed(1)} MB`
        : `${metrics.footprintKb} KB`,
      change: '~11 KB per correction',
      changeTone: 'neu',
    },
  ]

  return (
    <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {items.map((item) => (
        <GlassCard key={item.label} className="p-5">
          <div className="mb-2 text-[12px] font-medium text-[var(--color-body)]">
            {item.label}
          </div>
          <div className="font-[var(--font-heading)] text-[26px] sm:text-[32px] font-bold tabular-nums text-gradient-brand break-words">
            {item.value}
          </div>
          {item.change && (
            <div
              className={`mt-1 text-[12px] font-medium ${
                item.changeTone === 'pos' ? 'text-[var(--color-success)]'
                  : item.changeTone === 'neg' ? 'text-[var(--color-destructive)]'
                    : 'text-[var(--color-accent-blue)]'
              }`}
            >
              {item.change}
            </div>
          )}
        </GlassCard>
      ))}
    </div>
  )
}
