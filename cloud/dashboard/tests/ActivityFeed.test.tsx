import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

// Mock useApi BEFORE importing the component under test
const useApiMock = vi.fn()
vi.mock('@/hooks/useApi', () => ({
  useApi: (...args: unknown[]) => useApiMock(...args),
}))

import { ActivityFeed } from '@/components/brain/ActivityFeed'

beforeEach(() => {
  useApiMock.mockReset()
})

const noData = { data: null, loading: false, error: null, refetch: () => {} }
const withData = <T,>(data: T) => ({ data, loading: false, error: null, refetch: () => {} })

describe('ActivityFeed', () => {
  it('falls back to fixtures (demo data) when no real activity exists', () => {
    useApiMock.mockImplementation((url: string | null) => {
      if (url === '/brains') return withData([{ id: 'b1' }])
      return withData([])
    })
    render(<ActivityFeed />)
    expect(screen.getByText(/demo data/i)).toBeInTheDocument()
    // mockActivity has 6 entries — at least one expected title shows
    expect(screen.getByText(/Rule graduated/i)).toBeInTheDocument()
  })

  it('uses real activity data when the endpoint returns events', () => {
    const events = [
      {
        id: 'e1',
        brain_id: 'b1',
        type: 'graduation',
        source: 'src',
        data: { title: 'real graduation event' },
        tags: [],
        session: 1,
        created_at: new Date(Date.now() - 3600_000).toISOString(),
      },
    ]
    useApiMock.mockImplementation((url: string | null) => {
      if (url === '/brains') return withData([{ id: 'b1' }])
      return withData(events)
    })
    render(<ActivityFeed />)
    expect(screen.queryByText(/demo data/i)).not.toBeInTheDocument()
    expect(screen.getByText(/real graduation event/)).toBeInTheDocument()
  })

  it('normalizes meta-rule-emerged → meta-rule (renders the title)', () => {
    const events = [
      {
        id: 'e2',
        brain_id: 'b1',
        type: 'meta-rule-emerged',
        source: 'src',
        data: { title: 'a meta-rule appeared' },
        tags: [],
        session: 1,
        created_at: new Date(Date.now() - 7200_000).toISOString(),
      },
    ]
    useApiMock.mockImplementation((url: string | null) => {
      if (url === '/brains') return withData([{ id: 'b1' }])
      return withData(events)
    })
    render(<ActivityFeed />)
    expect(screen.getByText(/Meta-rule emerged/)).toBeInTheDocument()
    expect(screen.getByText(/a meta-rule appeared/)).toBeInTheDocument()
  })

  it('renders without crashing when there are no brains', () => {
    useApiMock.mockImplementation(() => noData)
    expect(() => render(<ActivityFeed />)).not.toThrow()
  })
})

// ---------------------------------------------------------------------------
// Outcome-first prop-driven mode
// ---------------------------------------------------------------------------

const at = (hoursAgo: number) => new Date(Date.now() - hoursAgo * 3_600_000).toISOString()

describe('ActivityFeed outcome reframes', () => {
  beforeEach(() => {
    useApiMock.mockImplementation(() => noData)
  })

  it('renders "Rule graduated" label for rule.graduated kind', () => {
    render(
      <ActivityFeed
        events={[{ id: '1', kind: 'rule.graduated', description: 'Attach case studies as PDF', at: at(2) }] as any}
      />,
    )
    expect(screen.getByText(/Rule graduated/i)).toBeInTheDocument()
    expect(screen.getByText(/Attach case studies/i)).toBeInTheDocument()
  })

  it('renders "Rule refined" label for rule.patched kind', () => {
    render(
      <ActivityFeed
        events={[{ id: '2', kind: 'rule.patched', description: 'No em dashes', at: at(24) }] as any}
      />,
    )
    expect(screen.getByText(/Rule refined/i)).toBeInTheDocument()
  })

  it('renders "Slipped" label for rule.recurrence kind', () => {
    render(
      <ActivityFeed
        events={[{ id: '3', kind: 'rule.recurrence', description: 'Colons over dashes', at: at(48) }] as any}
      />,
    )
    expect(screen.getByText(/Slipped/i)).toBeInTheDocument()
  })

  it('does NOT render meta_rule.emerged events', () => {
    render(
      <ActivityFeed
        events={[{ id: '4', kind: 'meta_rule.emerged', description: 'Verify before acting', at: at(72) }] as any}
      />,
    )
    expect(screen.queryByText(/Meta-rule/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Verify before acting/i)).not.toBeInTheDocument()
  })

  it('renders empty-state copy when no rendered events exist', () => {
    render(<ActivityFeed events={[{ id: '5', kind: 'meta_rule.emerged', description: 'x', at: at(1) }] as any} />)
    expect(screen.getByText(/brain is quiet/i)).toBeInTheDocument()
  })
})
