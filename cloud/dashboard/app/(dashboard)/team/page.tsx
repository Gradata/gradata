'use client'

import Link from 'next/link'
import { GlassCard } from '@/components/layout/GlassCard'
import { PlanGate, type PlanTier } from '@/components/brain/PlanBadge'
import { isOperatorEmail } from '@/lib/operator'
import { useApi } from '@/hooks/useApi'
import type { UserProfile } from '@/types/api'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'

interface TeamMemberStat {
  user_id: string
  display_name: string | null
  email: string | null
  role: string
  last_sync_at: string | null
  corrections_week: number
  correction_delta_pct: number
  rules_graduated_30d: number
  active: boolean
}

interface TeamStats {
  corrections_week: number
  rules_graduated_30d: number
  avg_delta_pct: number
  active_brains: number
  total_members: number
  members: TeamMemberStat[]
}

export default function TeamOverviewPage() {
  const { data: profile, loading: loadingProfile } = useApi<UserProfile>('/users/me')
  const workspaceId = profile?.workspaces?.[0]?.id ?? null
  const { data: stats, loading: loadingStats } = useApi<TeamStats>(
    workspaceId ? `/workspaces/${workspaceId}/team-stats` : null,
  )

  if (loadingProfile) return <LoadingSpinner className="py-20" />

  const currentPlan = (profile?.plan?.toLowerCase() ?? 'free') as PlanTier
  const agg = stats ?? {
    corrections_week: 0, rules_graduated_30d: 0, avg_delta_pct: 0,
    active_brains: 0, total_members: 0, members: [],
  }
  // Leaderboard: rank by most negative delta (whose AI learned fastest).
  const leaderboard = [...agg.members]
    .filter((m) => m.active)
    .sort((a, b) => a.correction_delta_pct - b.correction_delta_pct)

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

      <PlanGate current={currentPlan} requires="team" featureName="Team analytics" bypass={isOperatorEmail(profile?.email)}>
        {loadingStats ? (
          <LoadingSpinner className="py-12" />
        ) : (
          <>
            <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Kpi label="Team Corrections"   value={agg.corrections_week.toString()} sub="this week" tone="neu" />
              <Kpi label="Avg Δ vs last week" value={`${agg.avg_delta_pct > 0 ? '+' : ''}${agg.avg_delta_pct.toFixed(0)}%`}
                   sub={agg.avg_delta_pct < 0 ? 'learning' : agg.avg_delta_pct > 0 ? 'regressing' : 'flat'}
                   tone={agg.avg_delta_pct < 0 ? 'pos' : agg.avg_delta_pct > 0 ? 'neg' : 'neu'} />
              <Kpi label="Rules Graduated"    value={agg.rules_graduated_30d.toString()} sub="team · last 30 days" tone="neu" />
              <Kpi label="Active Brains"      value={`${agg.active_brains}/${agg.total_members}`} sub="synced in last 14d" tone="neu" />
            </div>

            <GlassCard gradTop>
              <div className="mb-5 flex items-baseline justify-between">
                <h3 className="text-[15px] font-semibold">Leaderboard</h3>
                <span className="text-[12px] text-[var(--color-body)]">
                  whose AI learned fastest
                </span>
              </div>
              {leaderboard.length === 0 ? (
                <p className="py-6 text-center text-[13px] text-[var(--color-body)]">
                  No active members yet. Once your team starts logging corrections, the leaderboard appears here.
                </p>
              ) : (
                <ul className="space-y-3">
                  {leaderboard.map((m, i) => (
                    <LeaderRow key={m.user_id} member={m} rank={i + 1} />
                  ))}
                </ul>
              )}
              <p className="mt-6 text-[11px] text-[var(--color-body)]">
                Ranked by week-over-week correction-rate decrease. Not for shaming — for pattern sharing.
              </p>
            </GlassCard>
          </>
        )}
      </PlanGate>
    </>
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

function LeaderRow({ member, rank }: { member: TeamMemberStat; rank: number }) {
  const deltaTone =
    member.correction_delta_pct < 0 ? 'text-[var(--color-success)]'
      : member.correction_delta_pct > 0 ? 'text-[var(--color-destructive)]'
        : 'text-[var(--color-body)]'
  return (
    <li className="flex flex-wrap items-center gap-x-4 gap-y-3 rounded-[0.5rem] border border-[var(--color-border)] bg-white/[0.02] p-3 sm:flex-nowrap">
      <span className="w-6 font-mono text-[12px] text-[var(--color-body)]">#{rank}</span>
      <div className="min-w-0 flex-1 basis-[calc(100%-3rem)] sm:basis-auto">
        <div className="text-[13px] font-medium truncate">
          {member.display_name || member.email || member.user_id.slice(0, 8)}
        </div>
        {member.email && member.display_name && (
          <div className="font-mono text-[10px] text-[var(--color-body)] truncate">{member.email}</div>
        )}
      </div>
      <div className="flex-1 sm:w-28 sm:flex-none sm:text-right">
        <div className={`font-mono text-[13px] tabular-nums ${deltaTone}`}>
          {member.correction_delta_pct > 0 ? '+' : ''}{member.correction_delta_pct.toFixed(0)}%
        </div>
        <div className="font-mono text-[10px] text-[var(--color-body)]">corrections Δ</div>
      </div>
      <div className="flex-1 sm:w-20 sm:flex-none sm:text-right">
        <div className="font-mono text-[13px] tabular-nums">{member.rules_graduated_30d}</div>
        <div className="font-mono text-[10px] text-[var(--color-body)]">rules 30d</div>
      </div>
      <div className="flex-1 sm:w-24 sm:flex-none sm:text-right">
        <div className="font-mono text-[13px] tabular-nums">{member.corrections_week}</div>
        <div className="font-mono text-[10px] text-[var(--color-body)]">this week</div>
      </div>
    </li>
  )
}
