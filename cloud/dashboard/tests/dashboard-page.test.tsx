import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

// Mock api/supabase so transitive imports don't blow up on missing env vars
// (ABProofPanel still exists in src/ even after demotion; only /proof uses it)
vi.mock('@/lib/api', () => ({
  default: { get: vi.fn().mockResolvedValue({ data: { available: false } }) },
}))

import DashboardPage from '../app/(dashboard)/dashboard/page'

// Mock useApi to return minimal shape
vi.mock('@/hooks/useApi', () => ({
  useApi: (url: string | null) => ({
    data:
      url === '/brains' ? [{ id: 'b1', name: 'Test' }] :
      url?.includes('/analytics') ? {
        total_lessons: 0, total_corrections: 0, graduation_rate: 0,
        avg_confidence: 0, lessons_by_state: {}, corrections_by_severity: {}, corrections_by_category: {},
      } :
      url?.includes('/corrections') ? { data: [] } :
      url?.includes('/lessons') ? { data: [] } :
      null,
    loading: false,
  }),
}))

describe('/dashboard page composition', () => {
  it('does NOT render MetaRulesGrid', () => {
    render(<DashboardPage />)
    expect(screen.queryByText(/meta rule/i)).not.toBeInTheDocument()
  })

  it('does NOT render PrivacyPosturePanel', () => {
    render(<DashboardPage />)
    expect(screen.queryByText(/privacy posture/i)).not.toBeInTheDocument()
  })

  it('does NOT render ABProofPanel', () => {
    render(<DashboardPage />)
    expect(screen.queryByText(/a\/b proof|ablation/i)).not.toBeInTheDocument()
  })

  it('does NOT render MethodologyLink', () => {
    render(<DashboardPage />)
    expect(screen.queryByText(/methodology/i)).not.toBeInTheDocument()
  })

  it('renders KpiStrip and ActiveRulesPanel (core outcome panels)', () => {
    render(<DashboardPage />)
    expect(screen.getByText('Time Saved')).toBeInTheDocument()
    expect(screen.getByText('Your Rules')).toBeInTheDocument()
  })
})
