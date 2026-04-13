'use client'

import { useMemo } from 'react'
import { GlassCard } from '@/components/layout/GlassCard'
import { useApi } from '@/hooks/useApi'
import type { Brain } from '@/types/api'
import { mockMetaRules, type MetaRuleTier, type MetaRuleLayer } from '@/lib/fixtures/mock-meta-rules'

/**
 * Meta-rule grid — 2-layer (Objective / Subjective) with Goal Alignment
 * as governing node (SIM101 consensus + SIM102 R5).
 *
 * Uses real /brains/{id}/meta-rules endpoint when available, falls back
 * to fixtures when there are no meta-rules yet (empty state — pre-launch
 * or cold start, we keep the demo visible so the surface isn't blank).
 */

interface ApiMetaRule {
  id: string
  brain_id: string
  title: string
  description: string
  source_lesson_ids: string[]
  created_at: string
}

interface DisplayMetaRule {
  id: string
  title: string
  layer: MetaRuleLayer
  tier: MetaRuleTier
  source_description: string
  source_categories: string[]
  is_real: boolean
}

const TIER_STYLE: Record<MetaRuleTier, string> = {
  universal: 'bg-[rgba(34,197,94,0.12)] text-[var(--color-success)]',
  strong:    'bg-[rgba(58,130,255,0.12)] text-[var(--color-accent-blue)]',
  minority:  'bg-[rgba(234,179,8,0.12)] text-[var(--color-warning)]',
}

/**
 * Heuristic layer assignment until backend carries it explicitly:
 * - Goal Alignment references → goal
 * - Factual / Clarity references → objective
 * - Tone / Domain / Actionability → subjective
 */
function inferLayer(title: string, description: string): MetaRuleLayer {
  const text = `${title} ${description}`.toLowerCase()
  if (/goal|intent|purpose/.test(text)) return 'goal'
  if (/fact|claim|accuracy|clarity|structure|concise/.test(text)) return 'objective'
  return 'subjective'
}

function inferTier(sourceCount: number): MetaRuleTier {
  if (sourceCount >= 5) return 'universal'
  if (sourceCount >= 3) return 'strong'
  return 'minority'
}

export function MetaRulesGrid() {
  const { data: brains } = useApi<Brain[]>('/brains')
  const primaryId = brains?.[0]?.id ?? null
  const { data: real } = useApi<ApiMetaRule[]>(
    primaryId ? `/brains/${primaryId}/meta-rules` : null,
  )

  const displayRules = useMemo<DisplayMetaRule[]>(() => {
    if (real && real.length > 0) {
      return real.map((r) => ({
        id: r.id,
        title: r.title,
        layer: inferLayer(r.title, r.description),
        tier: inferTier(r.source_lesson_ids?.length ?? 0),
        source_description: `From ${r.source_lesson_ids?.length ?? 0} lessons`,
        source_categories: [],
        is_real: true,
      }))
    }
    // Fallback: demo data flagged so empty-state styling can differ later
    return mockMetaRules.map((m) => ({
      id: m.id,
      title: m.title,
      layer: m.layer,
      tier: m.tier,
      source_description: m.source_description,
      source_categories: m.source_categories,
      is_real: false,
    }))
  }, [real])

  const goal       = displayRules.filter((m) => m.layer === 'goal')
  const objective  = displayRules.filter((m) => m.layer === 'objective')
  const subjective = displayRules.filter((m) => m.layer === 'subjective')
  const showingDemo = displayRules.every((r) => !r.is_real)

  const Card = ({ m }: { m: DisplayMetaRule }) => (
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
      {m.source_categories.length > 0 && (
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
      )}
    </li>
  )

  return (
    <GlassCard gradTop>
      <div className="mb-5 flex items-baseline justify-between">
        <h3 className="text-[15px] font-semibold">Meta Rules</h3>
        <span className="text-[12px] text-[var(--color-body)]">
          {showingDemo ? 'demo data — yours appear after 3+ related rules graduate' : '2-layer · goal governs'}
        </span>
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
