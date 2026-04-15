import { describe, it, expect } from 'vitest'
import type { TeamMember } from '@/types/api'
import {
  computeTeamAggregate,
  formatSyncAgo,
  isMemberActive,
  normalizeRole,
  pickWorkspaceId,
} from '@/lib/team'

const mk = (overrides: Partial<TeamMember> = {}): TeamMember => ({
  user_id: overrides.user_id ?? 'u1',
  email: overrides.email ?? 'a@b.co',
  display_name: overrides.display_name ?? 'Name',
  role: overrides.role ?? 'member',
  joined_at: overrides.joined_at ?? null,
  last_sync_at: overrides.last_sync_at ?? null,
})

const NOW = new Date('2026-01-01T00:00:00Z').getTime()

describe('isMemberActive', () => {
  it('returns false when last_sync_at is null', () => {
    expect(isMemberActive(mk({ last_sync_at: null }), NOW)).toBe(false)
  })

  it('returns true when synced within 14 days', () => {
    const sync = new Date(NOW - 3 * 24 * 3600 * 1000).toISOString()
    expect(isMemberActive(mk({ last_sync_at: sync }), NOW)).toBe(true)
  })

  it('returns false when synced more than 14 days ago', () => {
    const sync = new Date(NOW - 15 * 24 * 3600 * 1000).toISOString()
    expect(isMemberActive(mk({ last_sync_at: sync }), NOW)).toBe(false)
  })

  it('returns false for garbage timestamps', () => {
    expect(isMemberActive(mk({ last_sync_at: 'not-a-date' }), NOW)).toBe(false)
  })
})

describe('computeTeamAggregate', () => {
  it('counts total and active', () => {
    const recent = new Date(NOW - 60_000).toISOString()
    const stale = new Date(NOW - 30 * 24 * 3600 * 1000).toISOString()
    const members = [
      mk({ user_id: 'a', last_sync_at: recent }),
      mk({ user_id: 'b', last_sync_at: recent }),
      mk({ user_id: 'c', last_sync_at: stale }),
      mk({ user_id: 'd', last_sync_at: null }),
    ]
    const agg = computeTeamAggregate(members, NOW)
    expect(agg.totalMembers).toBe(4)
    expect(agg.activeBrains).toBe(2)
  })

  it('handles empty roster', () => {
    expect(computeTeamAggregate([], NOW)).toEqual({ totalMembers: 0, activeBrains: 0 })
  })
})

describe('formatSyncAgo', () => {
  it('returns "never synced" for null', () => {
    expect(formatSyncAgo(null, NOW)).toBe('never synced')
  })

  it('returns "just now" for very recent', () => {
    const t = new Date(NOW - 30_000).toISOString()
    expect(formatSyncAgo(t, NOW)).toBe('just now')
  })

  it('returns minutes for <1h', () => {
    const t = new Date(NOW - 5 * 60_000).toISOString()
    expect(formatSyncAgo(t, NOW)).toBe('5m ago')
  })

  it('returns hours for <24h', () => {
    const t = new Date(NOW - 3 * 3600_000).toISOString()
    expect(formatSyncAgo(t, NOW)).toBe('3h ago')
  })

  it('returns days for older', () => {
    const t = new Date(NOW - 5 * 24 * 3600_000).toISOString()
    expect(formatSyncAgo(t, NOW)).toBe('5d ago')
  })

  it('returns "never synced" for invalid ISO', () => {
    expect(formatSyncAgo('bogus', NOW)).toBe('never synced')
  })
})

describe('normalizeRole', () => {
  it('accepts the three canonical roles case-insensitively', () => {
    expect(normalizeRole('Owner')).toBe('owner')
    expect(normalizeRole('ADMIN')).toBe('admin')
    expect(normalizeRole('member')).toBe('member')
  })

  it('falls back to member for unknown or empty', () => {
    expect(normalizeRole(null)).toBe('member')
    expect(normalizeRole(undefined)).toBe('member')
    expect(normalizeRole('god')).toBe('member')
  })
})

describe('pickWorkspaceId', () => {
  it('returns null for empty/missing', () => {
    expect(pickWorkspaceId(undefined)).toBeNull()
    expect(pickWorkspaceId([])).toBeNull()
  })

  it('prefers owner-role workspace', () => {
    expect(
      pickWorkspaceId([
        { id: 'w1', role: 'member' },
        { id: 'w2', role: 'owner' },
        { id: 'w3', role: 'admin' },
      ]),
    ).toBe('w2')
  })

  it('falls back to first when no owner', () => {
    expect(
      pickWorkspaceId([
        { id: 'w1', role: 'member' },
        { id: 'w2', role: 'admin' },
      ]),
    ).toBe('w1')
  })
})
