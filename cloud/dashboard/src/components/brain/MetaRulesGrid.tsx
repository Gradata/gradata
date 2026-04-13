import { GlassCard } from '@/components/layout/GlassCard'
import { mockMetaRules, type MetaRuleTier } from '@/lib/fixtures/mock-meta-rules'

/**
 * Per SIM101 consensus + SIM102 R5: two-layer meta-rule grouping with
 * Goal Alignment as the governing node.
 *
 * - GOAL layer (top): Goal Alignment (always first-evaluated)
 * - OBJECTIVE layer: Factual Integrity, Clarity & Structure
 * - SUBJECTIVE layer: Tone & Register, Domain Fit, Actionability
 *
 * Each card gets a tier badge: Universal / Strong / Minority (SIM101 tiers).
 */

const TIER_STYLE: Record<MetaRuleTier, string> = {
  universal: 'bg-[rgba(34,197,94,0.12)] text-[var(--color-success)]',
  strong:    'bg-[rgba(58,130,255,0.12)] text-[var(--color-accent-blue)]',
  minority:  'bg-[rgba(234,179,8,0.12)] text-[var(--color-warning)]',
}

export function MetaRulesGrid() {
  // TODO(backend): fetch from /api/v1/brains/{id}/meta-rules when available
  const goal       = mockMetaRules.filter((m) => m.layer === 'goal')
  const objective  = mockMetaRules.filter((m) => m.layer === 'objective')
  const subjective = mockMetaRules.filter((m) => m.layer === 'subjective')

  const Card = ({ m }: { m: typeof mockMetaRules[number] }) => (
    <li className="rounded-[0.5rem] border border-[var(--color-border)] bg-white/[0.02] p-4 transition-all hover:border-[var(--color-border-hover)]">
      <div className="mb-2 flex items-start justify-between gap-3">
        <div className="text-[13px] leading-snug">{m.title}</div>
        <span className={`shrink-0 rounded-[0.25rem] px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wider ${TIER_STYLE[m.tier]}`}>
          {m.tier}
        </span>
      </div>
      <div className="mb-2 text-[11px] font-mono text-[var(--color-body)]">
        {m.source_description}
      </div>
      <div className="flex flex-wrap gap-1.5">
        {m.source_categories.map((cat) => (
          <span
            key={cat}
            className="rounded-[0.25rem] bg-[rgba(58,130,255,0.08)] px-2 py-0.5 text-[10px] font-medium text-[var(--color-accent-blue)]"
          >
            {cat}
          </span>
        ))}
      </div>
    </li>
  )

  return (
    <GlassCard gradTop>
      <div className="mb-5 flex items-baseline justify-between">
        <h3 className="text-[15px] font-semibold">Meta Rules</h3>
        <span className="text-[12px] text-[var(--color-body)]">2-layer · goal governs</span>
      </div>

      <div className="space-y-5">
        {goal.length > 0 && (
          <div>
            <div className="mb-2 font-mono text-[10px] uppercase tracking-wider text-[var(--color-accent-violet)]">
              Goal (governs all)
            </div>
            <ul className="space-y-3">{goal.map((m) => <Card key={m.id} m={m} />)}</ul>
          </div>
        )}
        {objective.length > 0 && (
          <div>
            <div className="mb-2 font-mono text-[10px] uppercase tracking-wider text-[var(--color-body)]">
              Objective
            </div>
            <ul className="space-y-3">{objective.map((m) => <Card key={m.id} m={m} />)}</ul>
          </div>
        )}
        {subjective.length > 0 && (
          <div>
            <div className="mb-2 font-mono text-[10px] uppercase tracking-wider text-[var(--color-body)]">
              Subjective
            </div>
            <ul className="space-y-3">{subjective.map((m) => <Card key={m.id} m={m} />)}</ul>
          </div>
        )}
      </div>
    </GlassCard>
  )
}
