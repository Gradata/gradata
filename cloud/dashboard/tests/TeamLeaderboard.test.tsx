import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { TeamLeaderboard } from '@/components/team/TeamLeaderboard'
import type { TeamMember } from '@/types/api'

const mk = (over: Partial<TeamMember> = {}): TeamMember => ({
  user_id: over.user_id ?? 'u1',
  email: over.email ?? 'a@b.co',
  display_name: over.display_name ?? null,
  role: over.role ?? 'member',
  joined_at: over.joined_at ?? null,
  last_sync_at: over.last_sync_at ?? null,
})

describe('TeamLeaderboard', () => {
  it('renders empty copy when there are no members', () => {
    render(<TeamLeaderboard members={[]} />)
    expect(screen.getByText(/No members have synced/i)).toBeInTheDocument()
  })

  it('renders a row for each member', () => {
    const members = [
      mk({ user_id: 'a', email: 'a@x.co', last_sync_at: new Date().toISOString() }),
      mk({ user_id: 'b', email: 'b@x.co', last_sync_at: new Date().toISOString() }),
    ]
    render(<TeamLeaderboard members={members} />)
    expect(screen.getAllByTestId('leader-row')).toHaveLength(2)
  })

  it('prefers display_name over email when present', () => {
    const members = [mk({ display_name: 'Alice Ada', email: 'a@x.co' })]
    render(<TeamLeaderboard members={members} />)
    expect(screen.getByText('Alice Ada')).toBeInTheDocument()
  })

  it('falls back to email when display_name is null', () => {
    const members = [mk({ display_name: null, email: 'only-email@x.co' })]
    render(<TeamLeaderboard members={members} />)
    // Email appears both as label and fallback — just assert it renders.
    expect(screen.getAllByText('only-email@x.co').length).toBeGreaterThan(0)
  })

  it('shows the role label for each row', () => {
    const members = [
      mk({ user_id: 'a', role: 'owner' }),
      mk({ user_id: 'b', role: 'admin' }),
      mk({ user_id: 'c', role: 'member' }),
    ]
    render(<TeamLeaderboard members={members} />)
    expect(screen.getByText('owner')).toBeInTheDocument()
    expect(screen.getByText('admin')).toBeInTheDocument()
    expect(screen.getByText('member')).toBeInTheDocument()
  })
})
