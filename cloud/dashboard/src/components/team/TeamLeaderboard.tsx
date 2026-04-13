import { GlassCard } from '@/components/layout/GlassCard'
import type { TeamMember } from '@/types/api'
import { formatSyncAgo } from '@/lib/team'

export function TeamLeaderboard({ members }: { members: TeamMember[] }) {
  return (
    <GlassCard gradTop>
      <div className="mb-5 flex items-baseline justify-between">
        <h3 className="text-[15px] font-semibold">Most recently active</h3>
        <span className="text-[12px] text-[var(--color-body)]">who&apos;s syncing</span>
      </div>
      {members.length === 0 ? (
        <p className="py-6 text-center text-[13px] text-[var(--color-body)]">
          No members have synced a brain yet.
        </p>
      ) : (
        <ul className="space-y-3">
          {members.map((m, i) => (
            <LeaderRow key={m.user_id} member={m} rank={i + 1} />
          ))}
        </ul>
      )}
      <p className="mt-6 text-[11px] text-[var(--color-body)]">
        Ranked by latest brain sync. Per-member correction trends land once analytics roll up server-side.
      </p>
    </GlassCard>
  )
}

function LeaderRow({ member, rank }: { member: TeamMember; rank: number }) {
  const displayName = member.display_name || member.email || member.user_id
  return (
    <li
      data-testid="leader-row"
      className="flex flex-wrap items-center gap-x-4 gap-y-3 rounded-[0.5rem] border border-[var(--color-border)] bg-white/[0.02] p-3 sm:flex-nowrap"
    >
      <span className="w-6 font-mono text-[12px] text-[var(--color-body)]">#{rank}</span>
      <div className="min-w-0 flex-1 basis-[calc(100%-3rem)] sm:basis-auto">
        <div className="text-[13px] font-medium truncate">{displayName}</div>
        <div className="font-mono text-[10px] text-[var(--color-body)] truncate">
          {member.email ?? '—'}
        </div>
      </div>
      <div className="flex-1 sm:w-32 sm:flex-none sm:text-right">
        <div className="font-mono text-[12px] text-[var(--color-body)]">
          {formatSyncAgo(member.last_sync_at)}
        </div>
        <div className="font-mono text-[10px] text-[var(--color-body)]">last sync</div>
      </div>
      <div className="flex-1 sm:w-20 sm:flex-none sm:text-right">
        <div className="font-mono text-[11px] uppercase tracking-wider text-[var(--color-body)]">
          {member.role}
        </div>
      </div>
    </li>
  )
}
