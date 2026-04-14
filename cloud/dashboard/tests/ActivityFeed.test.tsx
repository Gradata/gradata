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
