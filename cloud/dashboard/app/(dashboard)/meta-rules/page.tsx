'use client'

import { MetaRulesGrid } from '@/components/brain/MetaRulesGrid'
import { PlanGate, type PlanTier } from '@/components/brain/PlanBadge'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { useApi } from '@/hooks/useApi'
import type { UserProfile } from '@/types/api'

export default function MetaRulesPage() {
  const { data: profile, loading } = useApi<UserProfile>('/users/me')
  if (loading) return <LoadingSpinner className="py-20" />

  const currentPlan = (profile?.plan?.toLowerCase() ?? 'free') as PlanTier

  return (
    <>
      <header className="mb-7">
        <h1 className="text-[22px]">Meta Rules</h1>
        <p className="mt-1 text-[13px] text-[var(--color-body)]">
          Universal principles crystallized from 3+ source rules · 2-layer grouping with Goal Alignment governing
        </p>
      </header>

      <PlanGate current={currentPlan} requires="cloud" featureName="Meta rules">
        <MetaRulesGrid />
      </PlanGate>
    </>
  )
}
