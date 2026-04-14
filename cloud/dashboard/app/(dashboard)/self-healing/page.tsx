'use client'

import { useMemo, useState } from 'react'
import { GlassCard } from '@/components/layout/GlassCard'
import { Button } from '@/components/ui/button'
import { PlanGate, type PlanTier } from '@/components/brain/PlanBadge'
import { useApi } from '@/hooks/useApi'
import type { Brain, UserProfile } from '@/types/api'
import api from '@/lib/api'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { mockPatches, type PatchKind } from '@/lib/fixtures/mock-self-healing'

interface ApiPatch {
  id: string
  lesson_id: string
  old_description: string
  new_description: string
  reason: string
  created_at: string
}

interface DisplayPatch {
  id: string
  lesson_id: string
  kind: PatchKind
  old_description: string
  new_description: string
  reason: string
  created_at: string
  recurrence_change_pct: number | null
  is_real: boolean
}

const KIND_STYLE: Record<PatchKind, string> = {
  'auto-evolve':           'bg-[rgba(58,130,255,0.12)] text-[var(--color-accent-blue)]',
  'recurrence-fix':        'bg-[rgba(234,179,8,0.12)] text-[var(--color-warning)]',
  'contradiction-resolve': 'bg-[rgba(124,58,237,0.12)] text-[var(--color-accent-violet)]',
  'hook-promotion':        'bg-[rgba(34,197,94,0.12)] text-[var(--color-success)]',
}

/** Guess the patch kind from the reason string. Backend can ship explicit kind later. */
function inferKind(reason: string): PatchKind {
  const r = reason.toLowerCase()
  if (r.includes('rollback'))                          return 'auto-evolve'
  if (r.includes('recurr') || r.includes('misfire'))   return 'recurrence-fix'
  if (r.includes('conflict') || r.includes('contra'))  return 'contradiction-resolve'
  if (r.includes('hook') || r.includes('determinist')) return 'hook-promotion'
  return 'auto-evolve'
}

export default function SelfHealingPage() {
  const { data: profile, loading: loadingProfile } = useApi<UserProfile>('/users/me')
  const { data: brains } = useApi<Brain[]>('/brains')
  const primaryId = brains?.[0]?.id ?? null
  const { data: real, refetch } = useApi<ApiPatch[]>(
    primaryId ? `/brains/${primaryId}/rule-patches` : null,
  )
  const [rolledBack, setRolledBack] = useState<Record<string, boolean>>({})
  const [rollbackInFlight, setRollbackInFlight] = useState<string | null>(null)

  const patches = useMemo<DisplayPatch[]>(() => {
    if (real && real.length > 0) {
      return real.map((p) => ({
        id: p.id,
        lesson_id: p.lesson_id,
        kind: inferKind(p.reason),
        old_description: p.old_description,
        new_description: p.new_description,
        reason: p.reason,
        created_at: p.created_at,
        recurrence_change_pct: null,
        is_real: true,
      }))
    }
    return mockPatches.map((p) => ({
      id: p.id,
      lesson_id: p.lesson_id,
      kind: p.kind,
      old_description: p.old_description,
      new_description: p.new_description,
      reason: p.reason,
      created_at: p.created_at,
      recurrence_change_pct: p.recurrence_change_pct,
      is_real: false,
    }))
  }, [real])

  if (loadingProfile) return <LoadingSpinner className="py-20" />

  const currentPlan = (profile?.plan?.toLowerCase() ?? 'free') as PlanTier
  const showingDemo = patches.every((p) => !p.is_real)

  const handleRollback = async (patchId: string, isReal: boolean) => {
    if (!isReal) {
      setRolledBack((prev) => ({ ...prev, [patchId]: true }))
      return
    }
    if (!primaryId) return
    setRollbackInFlight(patchId)
    try {
      await api.post(`/brains/${primaryId}/rule-patches/${patchId}/rollback`)
      setRolledBack((prev) => ({ ...prev, [patchId]: true }))
      refetch()
    } finally {
      setRollbackInFlight(null)
    }
  }

  return (
    <>
      <header className="mb-7">
        <h1 className="text-[22px]">Self-Healing</h1>
        <p className="mt-1 text-[13px] text-[var(--color-body)]">
          When rules evolve on their own — audit trail with one-click rollback
          {showingDemo && ' · demo data — your patches appear here as rules self-correct'}
        </p>
      </header>

      <PlanGate current={currentPlan} requires="cloud" featureName="Self-healing audit trail">
        <ul className="space-y-4">
          {patches.map((p) => {
            const isRolledBack = rolledBack[p.id]
            const inFlight = rollbackInFlight === p.id
            return (
              <li key={p.id}>
                <GlassCard gradTop className={isRolledBack ? 'opacity-50' : ''}>
                  <div className="mb-3 flex items-baseline justify-between gap-3">
                    <span className={`rounded-[0.25rem] px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${KIND_STYLE[p.kind]}`}>
                      {p.kind.replace('-', ' ')}
                    </span>
                    <span className="font-mono text-[10px] text-[var(--color-body)]">
                      {formatAgo(p.created_at)} · lesson {p.lesson_id.slice(0, 8)}
                    </span>
                  </div>

                  <div className="space-y-2 text-[13px]">
                    <Diff label="before" text={p.old_description} tone="muted" />
                    <Diff label="after"  text={p.new_description} tone="bright" />
                  </div>

                  <div className="mt-4 flex items-center justify-between gap-3">
                    <div className="flex-1 text-[11px] text-[var(--color-body)]">
                      <span className="font-semibold">Why:</span> {p.reason}
                    </div>
                    <div className="flex items-center gap-3">
                      {p.recurrence_change_pct !== null && (
                        <div className="text-right">
                          <div className={`font-mono text-[13px] tabular-nums ${
                            p.recurrence_change_pct < 0
                              ? 'text-[var(--color-success)]'
                              : 'text-[var(--color-destructive)]'
                          }`}>
                            {p.recurrence_change_pct > 0 ? '+' : ''}{p.recurrence_change_pct}%
                          </div>
                          <div className="font-mono text-[10px] text-[var(--color-body)]">
                            recurrence
                          </div>
                        </div>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={isRolledBack || inFlight}
                        onClick={() => handleRollback(p.id, p.is_real)}
                      >
                        {isRolledBack ? 'Rolled back' : inFlight ? 'Rolling back…' : 'Rollback'}
                      </Button>
                    </div>
                  </div>
                </GlassCard>
              </li>
            )
          })}
        </ul>
      </PlanGate>
    </>
  )
}

function Diff({ label, text, tone }: { label: string; text: string; tone: 'muted' | 'bright' }) {
  return (
    <div className="flex gap-3">
      <span className={`w-14 shrink-0 font-mono text-[10px] uppercase tracking-wider ${
        tone === 'muted' ? 'text-[var(--color-body)]' : 'text-[var(--color-accent-blue)]'
      }`}>
        {label}
      </span>
      <span className={tone === 'muted' ? 'text-[var(--color-body)] line-through decoration-[var(--color-body)]/40' : ''}>
        {text}
      </span>
    </div>
  )
}

function formatAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime()
  const h = Math.floor(diffMs / 3600_000)
  if (h < 1) return 'just now'
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}
