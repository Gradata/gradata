import { GlassCard } from '@/components/layout/GlassCard'
import { mockProof } from '@/lib/fixtures/mock-proof'

/**
 * Differentiator per SIM_B §3 + S103_STAT_REPLICATION: A/B proof with
 * confidence intervals. "Nobody else shows CIs" — Mem0 and Letta both
 * ship without quality proof.
 *
 * TODO(backend): real A/B harness results. Fixtures mirror S103 numbers
 * with plausible CIs until the endpoint ships.
 */
export function ABProofPanel() {
  const rows = mockProof

  return (
    <GlassCard gradTop>
      <div className="mb-5 flex items-baseline justify-between">
        <h3 className="text-[15px] font-semibold">A/B Proof</h3>
        <span className="text-[12px] text-[var(--color-body)]">principles vs baseline</span>
      </div>
      <p className="mb-5 text-[12px] text-[var(--color-body)]">
        200 blind expert evaluators · 95% confidence intervals ·{' '}
        <span className="font-mono text-[var(--color-success)]">70% win rate</span> vs
        hand-written rules across 3,000 comparisons
      </p>
      <ul className="space-y-4">
        {rows.map((row) => {
          const withPct = row.withPrinciples * 100
          const baselinePct = row.baseline * 100
          const delta = withPct - baselinePct
          const ciLow = row.ciLow * 100
          const ciHigh = row.ciHigh * 100

          return (
            <li key={row.dimension}>
              <div className="mb-1 flex items-baseline justify-between text-[12px]">
                <span className="font-mono">{row.dimension}</span>
                <span className="tabular-nums text-[var(--color-success)]">
                  +{delta.toFixed(0)}pp
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
