import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

const useApiMock = vi.fn()
vi.mock('@/hooks/useApi', () => ({
  useApi: (...args: unknown[]) => useApiMock(...args),
}))

import { MetaRulesGrid } from '@/components/brain/MetaRulesGrid'

beforeEach(() => {
  useApiMock.mockReset()
})

const withData = <T,>(data: T) => ({ data, loading: false, error: null, refetch: () => {} })

describe('MetaRulesGrid', () => {
  it('renders all three layer headers from fixtures (goal/objective/subjective)', () => {
    useApiMock.mockImplementation((url: string | null) => {
      if (url === '/brains') return withData([{ id: 'b1' }])
      return withData([])
    })
    render(<MetaRulesGrid />)
    expect(screen.getByText(/Goal \(governs all\)/i)).toBeInTheDocument()
    expect(screen.getByText('Objective')).toBeInTheDocument()
    expect(screen.getByText('Subjective')).toBeInTheDocument()
  })

  it('shows demo-data note when no real meta-rules exist', () => {
    useApiMock.mockImplementation((url: string | null) => {
      if (url === '/brains') return withData([{ id: 'b1' }])
      return withData([])
    })
    render(<MetaRulesGrid />)
    expect(screen.getByText(/demo data/i)).toBeInTheDocument()
  })

  it('applies tier-specific styling (universal vs strong vs minority)', () => {
    useApiMock.mockImplementation((url: string | null) => {
      if (url === '/brains') return withData([{ id: 'b1' }])
      return withData([])
    })
    render(<MetaRulesGrid />)
    const universal = screen.getAllByText('universal')[0]
    expect(universal.className).toContain('text-[var(--color-success)]')

    const strong = screen.getAllByText('strong')[0]
    expect(strong.className).toContain('text-[var(--color-accent-blue)]')

    const minority = screen.getAllByText('minority')[0]
    expect(minority.className).toContain('text-[var(--color-warning)]')
  })

  it('uses real meta-rules when API returns data and infers tier from source count', () => {
    const real = [
      {
        id: 'mr1',
        brain_id: 'b1',
        title: 'verify the goal first',
        description: 'goal alignment matters',
        source_lesson_ids: ['l1', 'l2', 'l3', 'l4', 'l5'], // → universal
        created_at: new Date().toISOString(),
      },
    ]
    useApiMock.mockImplementation((url: string | null) => {
      if (url === '/brains') return withData([{ id: 'b1' }])
      return withData(real)
    })
    render(<MetaRulesGrid />)
    expect(screen.getByText(/verify the goal first/)).toBeInTheDocument()
    expect(screen.getByText('universal')).toBeInTheDocument()
    expect(screen.queryByText(/demo data/i)).not.toBeInTheDocument()
  })
})
