import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// Mock api/supabase so transitive imports don't blow up on missing env vars
// (ABProofPanel still exists in src/ even after demotion; only /proof uses it)
vi.mock('@/lib/api', () => ({
  default: { get: vi.fn().mockResolvedValue({ data: { available: false } }) },
}))

// Default mock: one brain with empty data. Individual tests can override
// via brainsOverride below.
let brainsOverride: unknown = undefined
vi.mock('@/hooks/useApi', () => ({
  useApi: (url: string | null) => ({
    data:
      url === '/brains' ? (brainsOverride !== undefined ? brainsOverride : [{ id: 'b1', name: 'Test' }]) :
      url?.includes('/analytics') ? {
        total_lessons: 0, total_corrections: 0, graduation_rate: 0,
        avg_confidence: 0, lessons_by_state: {}, corrections_by_severity: {}, corrections_by_category: {},
      } :
      url?.includes('/corrections') ? { data: [] } :
      url?.includes('/lessons') ? { data: [] } :
      url?.includes('/activity') ? [] :
      null,
    loading: false,
  }),
}))

import DashboardPage from '../app/(dashboard)/dashboard/page'

beforeEach(() => {
  brainsOverride = undefined
})

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

describe('/dashboard preview-with-sample-data flow', () => {
  it('lets a brain-less user enter and exit demo mode', async () => {
    brainsOverride = []
    const user = userEvent.setup()
    render(<DashboardPage />)

    // Empty state visible
    const previewBtn = screen.getByRole('button', { name: /Preview with sample data/i })
    expect(previewBtn).toBeInTheDocument()
    expect(screen.getByText(/AI that learns the corrections/i)).toBeInTheDocument()

    // Enter demo
    await user.click(previewBtn)
    expect(screen.getByText(/Demo mode/i)).toBeInTheDocument()
    // Fixture-backed panels render
    expect(screen.getByText('Time Saved')).toBeInTheDocument()
    expect(screen.getByText('Your Rules')).toBeInTheDocument()
    // Demo lessons appear (from demo-dashboard fixture). Use getAllByText
    // because a graduated lesson's description also surfaces in the decay
    // curve's SVG <title> tooltip on its graduation marker.
    expect(screen.getAllByText(/Never use em dashes/i).length).toBeGreaterThan(0)

    // Exit demo
    await user.click(screen.getByRole('button', { name: /Exit demo/i }))
    expect(screen.queryByText(/Demo mode/i)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Preview with sample data/i })).toBeInTheDocument()
  })
})
