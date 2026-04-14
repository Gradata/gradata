import { GlassCard } from '@/components/layout/GlassCard'
import type { BrainAnalytics } from '@/types/api'

/**
 * 6-dimension sim-validated taxonomy (WAVE2 §2-3, SIM102 R5). Maps legacy
 * backend categories into the new dimensions for display. Backend will
 * eventually ship these natively (TODO).
 *
 * Legacy 5 buckets (TONE, DRAFTING, FORMAT, PROCESS, ACCURACY) fold like:
 * - TONE        → Tone & Register
 * - DRAFTING    → Clarity & Structure
 * - FORMAT      → Clarity & Structure
 * - PROCESS     → Actionability
 * - ACCURACY    → Factual Integrity
 * Unknown / null → bucketed to Factual Integrity (safest default).
 */
const LEGACY_MAP: Record<string, string> = {
  TONE: 'Tone & Register',
  DRAFTING: 'Clarity & Structure',
  FORMAT: 'Clarity & Structure',
  PROCESS: 'Actionability',
  ACCURACY: 'Factual Integrity',
  'Goal Alignment': 'Goal Alignment',
  'Tone & Register': 'Tone & Register',
  'Clarity & Structure': 'Clarity & Structure',
  'Factual Integrity': 'Factual Integrity',
  'Domain Fit': 'Domain Fit',
  'Actionability': 'Actionability',
}

const DIMENSIONS = [
  'Goal Alignment',
  'Factual Integrity',
  'Clarity & Structure',
  'Domain Fit',
  'Tone & Register',
  'Actionability',
] as const

export function CategoriesChart({ analytics }: { analytics: BrainAnalytics }) {
  const folded: Record<string, number> = Object.fromEntries(
    DIMENSIONS.map((d) => [d, 0]),
  )

  for (const [key, count] of Object.entries(analytics.corrections_by_category ?? {})) {
    const mapped = LEGACY_MAP[key] ?? 'Factual Integrity'
    folded[mapped] = (folded[mapped] ?? 0) + (count as number)
  }

  const items = DIMENSIONS.map((d) => ({ dimension: d, count: folded[d] ?? 0 }))
  const max = Math.max(1, ...items.map((i) => i.count))

  return (
    <GlassCard gradTop>
      <div className="mb-5 flex items-baseline justify-between">
        <h3 className="text-[15px] font-semibold">Corrections by Dimension</h3>
        <span className="text-[12px] text-[var(--color-body)]">
          6-dim taxonomy (WAVE2)
        </span>
      </div>
      <ul className="space-y-3">
        {items.map((item) => {
          const pct = (item.count / max) * 100
          return (
            <li key={item.dimension}>
              <div className="mb-1 flex items-baseline justify-between text-[12px]">
                <span className="font-mono">{item.dimension}</span>
                <span className="tabular-nums text-[var(--color-body)]">{item.count}</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.04]">
                <div
                  className="h-full transition-all bg-gradient-brand"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </li>
          )
        })}
      </ul>
    </GlassCard>
  )
}
