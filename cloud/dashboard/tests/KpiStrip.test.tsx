import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { KpiStrip } from '@/components/brain/KpiStrip'
import type { KpiMetrics } from '@/lib/analytics-client'

const baseMetrics: KpiMetrics = {
  correctionRateDeltaPct: 0,
  correctionsThisWeek: 0,
  correctionsPriorWeek: 0,
  sessionsToGraduation: 0,
  sessionsToGraduationLow: 0,
  sessionsToGraduationHigh: 0,
  misfireCount: 0,
  totalFires: 0,
  footprintKb: 0,
}

describe('KpiStrip', () => {
  it('renders 4 KPI cards with their labels', () => {
    render(<KpiStrip metrics={baseMetrics} />)
    expect(screen.getByText('Correction Rate')).toBeInTheDocument()
    expect(screen.getByText('Sessions to Graduation')).toBeInTheDocument()
    expect(screen.getByText('Misfires')).toBeInTheDocument()
    expect(screen.getByText('Brain Footprint')).toBeInTheDocument()
  })

  it('shows "—" placeholder for zero correction rate and zero graduation', () => {
    render(<KpiStrip metrics={baseMetrics} />)
    const dashes = screen.getAllByText('—')
    // correction rate + sessions-to-graduation both render "—"
    expect(dashes.length).toBeGreaterThanOrEqual(2)
  })

  it('renders success tone (var --color-success) for negative delta', () => {
    const m: KpiMetrics = {
      ...baseMetrics,
      correctionRateDeltaPct: -42,
      correctionsThisWeek: 3,
      correctionsPriorWeek: 5,
    }
    render(<KpiStrip metrics={m} />)
    const change = screen.getByText('3 this week · 5 prior')
    expect(change.className).toContain('text-[var(--color-success)]')
  })

  it('renders destructive tone for misfires > 0', () => {
    const m: KpiMetrics = { ...baseMetrics, misfireCount: 2, totalFires: 10 }
    render(<KpiStrip metrics={m} />)
    const change = screen.getByText('across 10 rule fires')
    expect(change.className).toContain('text-[var(--color-destructive)]')
  })
})
