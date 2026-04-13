'use client'

import Link from 'next/link'
import { GlassCard } from '@/components/layout/GlassCard'
import { PlanGate, type PlanTier } from '@/components/brain/PlanBadge'
import { useApi } from '@/hooks/useApi'
import type { UserProfile } from '@/types/api'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { mockTeam, computeTeamAggregate, type MockMember } from '@/lib/fixtures/mock-team'

export default function TeamOverviewPage() {
  const { data: profile, loading } = useApi<UserProfile>('/users/me')
  if (loading) return <LoadingSpinner className="py-20" />

  const currentPlan = (profile?.plan?.toLowerCase() ?? 'free') as PlanTier
  const agg = computeTeamAggregate(mockTeam)
  // Leaderboard: rank by most negative correction_delta_pct (whose AI learned fastest)
  const leaderboard = [...mockTeam]
    .filter((m) => m.status === 'active')
    .sort((a, b) => a.correction_delta_pct - b.correction_delta_pct)

  return (
    <>
      <header className="mb-7 flex items-baseline justify-between">
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
        {/* 4 team KPI cards */}
        <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Kpi label="Team Corrections"   value={agg.correctionsWeek.toString()} sub="this week" tone="neu" />
          <Kpi label="Avg Δ vs last week" value={`${agg.avgDelta > 0 ? '+' : ''}${agg.avgDelta.toFixed(0)}%`}
               sub={agg.avgDelta < 0 ? 'learning' : 'regressing'}
               tone={agg.avgDelta < 0 ? 'pos' : agg.avgDelta > 0 ? 'neg' : 'neu'} />
          <Kpi label="Rules Graduated"    value={agg.rulesGraduated.toString()} sub="team · last 30 days" tone="neu" />
          <Kpi label="Avg Recurrence"     value={`${(agg.avgRecurrence * 100).toFixed(0)}%`}
               sub={`${agg.activeBrains}/${agg.totalMembers} active brains`}
               tone={agg.avgRecurrence < 0.10 ? 'pos' : 'neu'} />
        </div>

        {/* Leaderboard */}
        <GlassCard gradTop>
          <div className="mb-5 flex items-baseline justify-between">
            <h3 className="text-[15px] font-semibold">Leaderboard</h3>
            <span className="text-[12px] text-[var(--color-body)]">
              whose AI learned fastest
            </span>
          </div>
          <ul className="space-y-3">
            {leaderboard.map((m, i) => (
              <LeaderRow key={m.id} member={m} rank={i + 1} />
            ))}
          </ul>
          <p className="mt-6 text-[11px] text-[var(--color-body)]">
            Ranked by week-over-week correction-rate decrease. Not for shaming — for pattern sharing.
          </p>
        </GlassCard>
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
      <div className="font-[var(--font-heading)] text-[32px] font-bold tabular-nums text-gradient-brand">
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

function LeaderRow({ member, rank }: { member: MockMember; rank: number }) {
  const deltaTone =
    member.correction_delta_pct < 0 ? 'text-[var(--color-success)]'
      : member.correction_delta_pct > 0 ? 'text-[var(--color-destructive)]'
        : 'text-[var(--color-body)]'
  return (
    <li className="flex items-center gap-4 rounded-[0.5rem] border border-[var(--color-border)] bg-white/[0.02] p-3">
      <span className="w-6 font-mono text-[12px] text-[var(--color-body)]">#{rank}</span>
      <div className="flex-1 min-w-0">
        <div className="text-[13px] font-medium">{member.name}</div>
        <div className="font-mono text-[10px] text-[var(--color-body)]">{member.email}</div>
      </div>
      <div className="w-28 text-right">
        <div className={`font-mono text-[13px] tabular-nums ${deltaTone}`}>
          {member.correction_delta_pct > 0 ? '+' : ''}{member.correction_delta_pct.toFixed(0)}%
        </div>
        <div className="font-mono text-[10px] text-[var(--color-body)]">corrections Δ</div>
      </div>
      <div className="w-20 text-right">
        <div className="font-mono text-[13px] tabular-nums">{member.rules_graduated_30d}</div>
        <div className="font-mono text-[10px] text-[var(--color-body)]">rules 30d</div>
      </div>
      <div className="w-24 text-right">
        <div className="font-mono text-[13px] tabular-nums">{(member.recurrence_rate * 100).toFixed(0)}%</div>
        <div className="font-mono text-[10px] text-[var(--color-body)]">recurrence</div>
      </div>
    </li>
  )
}
