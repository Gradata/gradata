import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { KpiStrip } from '@/components/brain/KpiStrip'
import type { KpiMetrics } from '@/lib/analytics-client'

const baseMetrics: KpiMetrics = {
  correctionRateDeltaPct: 0,
  correctionsThisWeek: 0,
  correctionsPriorWeek: 0,
  correctionRateWoWDelta: null,
  sessionsToGraduation: 0,
  sessionsToGraduationLow: 0,
  sessionsToGraduationHigh: 0,
  misfireCount: 0,
  misfireCountPriorWeek: 0,
  misfireWoWDelta: null,
  totalFires: 0,
  footprintKb: 0,
  timeSavedMinutes: 0,
  timeSavedMinutesPriorWeek: null,
  timeSavedWoWDelta: null,
}

describe('KpiStrip', () => {
  it('renders all KPI card labels including Est. Time Saved', () => {
    render(<KpiStrip metrics={baseMetrics} />)
    expect(screen.getByText('Correction Rate')).toBeInTheDocument()
    expect(screen.getByText(/Est\. Time Saved/i)).toBeInTheDocument()
    expect(screen.getByText('Sessions to Graduation')).toBeInTheDocument()
    expect(screen.getByText('Misfires')).toBeInTheDocument()
    expect(screen.getByText('Brain Footprint')).toBeInTheDocument()
  })

  it('shows "—" placeholder for null/zero values', () => {
    render(<KpiStrip metrics={baseMetrics} />)
    const dashes = screen.getAllByText('—')
    // correction rate (null WoW) + sessions-to-graduation (0) + time saved (0) all render "—"
    expect(dashes.length).toBeGreaterThanOrEqual(2)
  })

  it('renders destructive tone for misfires > 0', () => {
    const m: KpiMetrics = { ...baseMetrics, misfireCount: 2, totalFires: 10 }
    render(<KpiStrip metrics={m} />)
    const change = screen.getByText(/across 10 rule fires/)
    expect(change.className).toContain('text-[var(--color-destructive)]')
  })
})

const fullMetrics: KpiMetrics = {
  correctionRateDeltaPct: -38,
  correctionsThisWeek: 23,
  correctionsPriorWeek: 37,
  correctionRateWoWDelta: -38,
  sessionsToGraduation: 2.3,
  sessionsToGraduationLow: 1.9,
  sessionsToGraduationHigh: 2.7,
  misfireCount: 0,
  misfireCountPriorWeek: 2,
  misfireWoWDelta: -100,
  totalFires: 120,
  footprintKb: 340,
  timeSavedMinutes: 93,
  timeSavedMinutesPriorWeek: null,
  timeSavedWoWDelta: null,
}

describe('KpiStrip with Time Saved', () => {
  it('renders five cards including Est. Time Saved', () => {
    render(<KpiStrip metrics={fullMetrics} />)
    expect(screen.getByText(/Correction Rate/i)).toBeInTheDocument()
    expect(screen.getByText(/Est\. Time Saved/i)).toBeInTheDocument()
    expect(screen.getByText(/Sessions to Graduation/i)).toBeInTheDocument()
    expect(screen.getByText(/Misfires/i)).toBeInTheDocument()
    expect(screen.getByText(/Brain Footprint/i)).toBeInTheDocument()
  })

  it('renders time saved as approximate hours when >= 60 min', () => {
    render(<KpiStrip metrics={fullMetrics} />)
    // 93 min = ~1.6h; component should render like "~1.6h" or "~1h 33m"
    expect(screen.getByText(/~1\.[56]h|~1h 3[0-9]m/)).toBeInTheDocument()
  })

  it('renders em dash for null WoW deltas', () => {
    render(<KpiStrip metrics={{ ...fullMetrics, correctionRateWoWDelta: null }} />)
    const card = screen.getByText(/Correction Rate/i).closest('div')!
    expect(card.textContent).toMatch(/—/)
  })

  it('includes the honest "Est." tooltip copy on the Time Saved card', () => {
    render(<KpiStrip metrics={fullMetrics} />)
    const timeSavedCard = screen.getByText(/Est\. Time Saved/i).closest('div')!
    const tip = timeSavedCard.querySelector('[title]')?.getAttribute('title')
      ?? timeSavedCard.getAttribute('title')
      ?? ''
    expect(tip).toMatch(/Estimated|3 minutes|fires/)
  })
})
