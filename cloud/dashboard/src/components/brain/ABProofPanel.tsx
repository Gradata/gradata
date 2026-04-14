'use client'

import { useEffect, useState } from 'react'
import { GlassCard } from '@/components/layout/GlassCard'
import api from '@/lib/api'
import { mockProof, type ABDimension } from '@/lib/fixtures/mock-proof'

/**
 * A/B Proof — consumes the ablation-backed /public/proof endpoint. When
 * live ablation data is present we show real numbers and real judge/trial
 * counts; when it isn't (fresh deploy) we fall back to demo data with a
 * visible banner so nothing on the panel is fabricated.
 */

interface ProofDim {
  dimension: string
  baseline_mean: number
  with_rules_mean: number | null
  with_full_mean: number | null
  best_mean: number
  ci_low: number
  ci_high: number
  delta_pp: number
  n_base: number
  n_with: number
}

interface ProofPayload {
  available: boolean
  source: string | null
  subjects?: string[]
  judge?: string
  trials?: number
  dimensions?: ProofDim[]
  reason?: string
}

// Scientific dim names → friendly labels
const DIM_LABELS: Record<string, string> = {
  correctness: 'Factual Integrity',
  preference_adherence: 'Preference Fit',
  quality: 'Overall Quality',
}

function formatModelList(models: string[] | undefined): string {
  if (!models || models.length === 0) return 'the subject models'
  if (models.length === 1) return models[0]
  if (models.length === 2) return models.join(' and ')
  return `${models.slice(0, -1).join(', ')}, and ${models[models.length - 1]}`
}

export function ABProofPanel() {
  const [data, setData] = useState<ProofPayload | null>(null)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    let mounted = true
    api
      .get<ProofPayload>('/public/proof')
      .then((res) => {
        if (mounted) {
          setData(res.data)
          setLoaded(true)
        }
      })
      .catch(() => {
        if (mounted) {
          setData({ available: false, source: null })
          setLoaded(true)
        }
      })
    return () => {
      mounted = false
    }
  }, [])

  // Pick rows: real dimensions if available, otherwise demo fixtures
  const live = data?.available && (data?.dimensions?.length ?? 0) > 0
  const rows: ABDimension[] = live
    ? (data!.dimensions ?? []).map((d) => ({
        dimension: DIM_LABELS[d.dimension] ?? d.dimension,
        baseline: d.baseline_mean,
        withPrinciples: d.best_mean,
        ciLow: d.ci_low,
        ciHigh: d.ci_high,
      }))
    : mockProof

  const trials = data?.trials ?? 0
  const subjectsLabel = formatModelList(data?.subjects)

  return (
    <GlassCard gradTop>
      <div className="mb-5 flex items-baseline justify-between">
        <h3 className="text-[15px] font-semibold">A/B Proof</h3>
        <span className="text-[12px] text-[var(--color-body)]">
          {live ? 'live · rules+meta vs baseline' : 'demo data — live numbers after first ablation'}
        </span>
      </div>
      <p className="mb-5 text-[12px] text-[var(--color-body)]">
        {loaded && live ? (
          <>
            {trials} blind judge calls across {subjectsLabel} · judge {data?.judge ?? 'haiku-4.5'} ·
            95% confidence intervals
          </>
        ) : (
          <>demo numbers shown below · real ablation lands on first judge pass</>
        )}
      </p>
      <ul className="space-y-4">
        {rows.map((row) => {
          const withPct = row.withPrinciples * 100
          const baselinePct = row.baseline * 100
          const delta = withPct - baselinePct
          const ciLow = row.ciLow * 100
          const ciHigh = row.ciHigh * 100
          const sign = delta >= 0 ? '+' : ''
          const deltaColor = delta >= 0 ? 'text-[var(--color-success)]' : 'text-[var(--color-destructive)]'

          return (
            <li key={row.dimension}>
              <div className="mb-1 flex items-baseline justify-between text-[12px]">
                <span className="font-mono">{row.dimension}</span>
                <span className={`tabular-nums ${deltaColor}`}>
                  {sign}{delta.toFixed(0)}pp
                </span>
              </div>
              <div className="mb-1 flex gap-1">
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/[0.04]">
                  <div
                    className="h-full bg-[var(--color-body)]"
                    style={{ width: `${baselinePct}%` }}
                    aria-label={`baseline ${baselinePct.toFixed(0)}%`}
                  />
                </div>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/[0.04]">
                  <div
                    className="h-full bg-gradient-brand"
                    style={{ width: `${withPct}%` }}
                    aria-label={`with principles ${withPct.toFixed(0)}%`}
                  />
                </div>
              </div>
              <div className="flex justify-between text-[10px] font-mono text-[var(--color-body)]">
                <span>baseline {baselinePct.toFixed(0)}%</span>
                <span>
                  with principles {withPct.toFixed(0)}% · 95% CI [{ciLow.toFixed(0)}, {ciHigh.toFixed(0)}]
                </span>
              </div>
            </li>
          )
        })}
      </ul>
    </GlassCard>
  )
}
