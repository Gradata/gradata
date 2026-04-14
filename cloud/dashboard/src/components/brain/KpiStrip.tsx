import { GlassCard } from '@/components/layout/GlassCard'
import type { KpiMetrics } from '@/lib/analytics-client'

const TIME_SAVED_TOOLTIP =
  'Estimated time saved = 3 minutes × rule fires on rules that have already caught a real correction. Excludes first-fire-ever. This is an estimate; the goal is a directional signal, not a precise audit.'

function formatMinutes(n: number): string {
  if (n < 60) return `${n}m`
  const hours = n / 60
  if (hours >= 10) return `~${Math.round(hours)}h`
  return `~${hours.toFixed(1)}h`
}

function formatDelta(n: number | null): string {
  if (n === null) return '—'
  if (n === 0) return '0%'
  return `${n > 0 ? '+' : ''}${n}%`
}

export function KpiStrip({ metrics }: { metrics: KpiMetrics }) {
  const items: Array<{
    label: string
    value: string
    subline?: string
    delta?: string
    tone?: 'pos' | 'neg' | 'neu'
    tooltip?: string
  }> = [
    {
      label: 'Correction Rate',
      value: metrics.correctionRateWoWDelta === null ? '—' : formatDelta(metrics.correctionRateWoWDelta),
      subline: `${metrics.correctionsThisWeek} this week · ${metrics.correctionsPriorWeek} prior`,
      delta: formatDelta(metrics.correctionRateWoWDelta),
      tone:
        metrics.correctionRateWoWDelta === null ? 'neu'
          : metrics.correctionRateWoWDelta < 0 ? 'pos'
            : metrics.correctionRateWoWDelta > 0 ? 'neg' : 'neu',
    },
    {
      label: 'Est. Time Saved',
      value: metrics.timeSavedMinutes === 0 ? '—' : formatMinutes(metrics.timeSavedMinutes),
      subline:
        metrics.timeSavedWoWDelta === null
          ? 'vs prior: —'
          : `vs prior: ${formatDelta(metrics.timeSavedWoWDelta)}`,
      tone: metrics.timeSavedMinutes > 0 ? 'pos' : 'neu',
      tooltip: TIME_SAVED_TOOLTIP,
    },
    {
      label: 'Sessions to Graduation',
      value: metrics.sessionsToGraduation === 0 ? '—' : metrics.sessionsToGraduation.toFixed(1),
      subline:
        metrics.sessionsToGraduation > 0
          ? `95% CI [${metrics.sessionsToGraduationLow}, ${metrics.sessionsToGraduationHigh}]`
          : 'awaiting first graduation',
      tone: 'neu',
    },
    {
      label: 'Misfires',
      value: metrics.misfireCount.toString(),
      subline:
        metrics.misfireWoWDelta === null
          ? `across ${metrics.totalFires} rule fires`
          : `was ${metrics.misfireCountPriorWeek} last week · ${formatDelta(metrics.misfireWoWDelta)}`,
      tone: metrics.misfireCount === 0 ? 'pos' : 'neg',
    },
    {
      label: 'Brain Footprint',
      value:
        metrics.footprintKb >= 1024
          ? `${(metrics.footprintKb / 1024).toFixed(1)} MB`
          : `${metrics.footprintKb} KB`,
      subline: '~11 KB per correction',
      tone: 'neu',
    },
  ]

  return (
    <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
      {items.map((item) => (
        <GlassCard key={item.label} className="p-5" title={item.tooltip}>
          <span className="mb-2 block text-[12px] font-medium text-[var(--color-body)]">
            {item.label}
          </span>
          <div className="font-[var(--font-heading)] text-[26px] sm:text-[28px] font-bold tabular-nums text-gradient-brand break-words">
            {item.value}
          </div>
          {item.subline && (
            <div
              className={`mt-1 text-[12px] font-medium ${
                item.tone === 'pos' ? 'text-[var(--color-success)]'
                  : item.tone === 'neg' ? 'text-[var(--color-destructive)]'
                    : 'text-[var(--color-accent-blue)]'
              }`}
            >
              {item.subline}
            </div>
          )}
        </GlassCard>
      ))}
    </div>
  )
}
