'use client'

import Link from 'next/link'
import { GlassCard } from '@/components/layout/GlassCard'
import { PlanGate, type PlanTier } from '@/components/brain/PlanBadge'
import { useApi } from '@/hooks/useApi'
import type { TeamMember, UserProfile } from '@/types/api'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { ErrorState } from '@/components/shared/ErrorState'
import { TeamLeaderboard } from '@/components/team/TeamLeaderboard'
import { computeTeamAggregate, pickWorkspaceId } from '@/lib/team'

export default function TeamOverviewPage() {
  const { data: profile, loading: profileLoading } = useApi<UserProfile>('/users/me')
  const workspaceId = pickWorkspaceId(profile?.workspaces)

  const {
    data: members,
    loading: membersLoading,
    error: membersError,
    refetch,
  } = useApi<TeamMember[]>(workspaceId ? `/workspaces/${workspaceId}/members` : null)

  if (profileLoading || membersLoading) return <LoadingSpinner className="py-20" />

  const currentPlan = (profile?.plan?.toLowerCase() ?? 'free') as PlanTier

  if (!workspaceId) {
    return <TeamEmptyState message="No workspace found for your account yet." />
  }
  if (membersError) return <ErrorState message={membersError} onRetry={refetch} />

  const roster = members ?? []
  const agg = computeTeamAggregate(roster)

  // Leaderboard: rank active members by most recent sync (no per-member delta
  // in the real API yet — sort by freshest activity as a proxy for engagement).
  const leaderboard = [...roster]
    .filter((m) => m.last_sync_at !== null)
    .sort((a, b) => {
      const aT = a.last_sync_at ? new Date(a.last_sync_at).getTime() : 0
      const bT = b.last_sync_at ? new Date(b.last_sync_at).getTime() : 0
      return bT - aT
    })

  return (
    <>
      <header className="mb-7 flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h1 className="text-[22px]">Team Overview</h1>
          <p className="mt-1 text-[13px] text-[var(--color-body)]">
            Whose patterns can we learn from?
          </p>
        </div>
        <Link
          href="/team/members"
          className="text-[12px] text-[var(--color-body)] underline-offset-4 hover:text-[var(--color-text)] hover:underline"
        >
          Members →
        </Link>
      </header>

      <PlanGate current={currentPlan} requires="team" featureName="Team analytics">
        <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Kpi label="Team members" value={agg.totalMembers.toString()} sub="on the roster" tone="neu" />
          <Kpi label="Active brains" value={agg.activeBrains.toString()}
               sub={`${agg.activeBrains}/${agg.totalMembers} synced recently`}
               tone={agg.activeBrains > 0 ? 'pos' : 'neu'} />
          <Kpi label="Owners + admins"
               value={roster.filter((m) => m.role === 'owner' || m.role === 'admin').length.toString()}
               sub="can manage team" tone="neu" />
          <Kpi label="Members" value={roster.filter((m) => m.role === 'member').length.toString()}
               sub="read-own-brain" tone="neu" />
        </div>

        <TeamLeaderboard members={leaderboard} />
      </PlanGate>
    </>
  )
}

function TeamEmptyState({ message }: { message: string }) {
  return (
    <div className="py-12 text-center">
      <h1 className="text-[22px]">Team Overview</h1>
      <p className="mt-3 text-[13px] text-[var(--color-body)]">{message}</p>
    </div>
  )
}

function Kpi({ label, value, sub, tone }: {
  label: string; value: string; sub?: string; tone: 'pos' | 'neg' | 'neu'
}) {
  return (
    <GlassCard className="p-5">
      <div className="mb-2 text-[12px] font-medium text-[var(--color-body)]">{label}</div>
      <div className="font-[var(--font-heading)] text-[26px] sm:text-[32px] font-bold tabular-nums text-gradient-brand break-words">
        {value}
      </div>
      {sub && (
        <div className={`mt-1 text-[12px] font-medium ${
          tone === 'pos' ? 'text-[var(--color-success)]'
            : tone === 'neg' ? 'text-[var(--color-destructive)]'
              : 'text-[var(--color-accent-blue)]'
        }`}>
          {sub}
        </div>
      )}
    </GlassCard>
  )
}

