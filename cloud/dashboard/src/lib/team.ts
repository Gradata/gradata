import type { TeamMember } from '@/types/api'
import { formatRelativeAgo } from '@/lib/format'

// 14 days mirrors the operator healthy-cutoff so the two surfaces stay consistent.
const ACTIVE_THRESHOLD_MS = 14 * 24 * 60 * 60 * 1000

export function isMemberActive(member: TeamMember, now: number = Date.now()): boolean {
  if (!member.last_sync_at) return false
  const synced = new Date(member.last_sync_at).getTime()
  if (Number.isNaN(synced)) return false
  return now - synced <= ACTIVE_THRESHOLD_MS
}

export interface TeamAggregate {
  totalMembers: number
  activeBrains: number
}

export function computeTeamAggregate(members: TeamMember[], now: number = Date.now()): TeamAggregate {
  const active = members.filter((m) => isMemberActive(m, now)).length
  return {
    totalMembers: members.length,
    activeBrains: active,
  }
}

/** Returns "never synced" when the timestamp is null/invalid. */
export function formatSyncAgo(iso: string | null, now: number = Date.now()): string {
  return formatRelativeAgo(iso, 'never synced', now)
}

/** Normalize a role string (defensive — backend may send any string). */
export function normalizeRole(role: string | undefined | null): 'owner' | 'admin' | 'member' {
  const r = (role || '').trim().toLowerCase()
  if (r === 'owner' || r === 'admin' || r === 'member') return r
  return 'member'
}

/** Pick the "primary" workspace id from a profile's workspaces list. */
export function pickWorkspaceId(
  workspaces: Array<{ id: string; role?: string }> | undefined,
): string | null {
  if (!workspaces || workspaces.length === 0) return null
  // Prefer the workspace where the user is an owner, else first.
  const owned = workspaces.find((w) => (w.role || '').trim().toLowerCase() === 'owner')
  return (owned ?? workspaces[0]).id
}
