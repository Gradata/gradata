import { describe, it, expect } from 'vitest'
import { render, screen, within } from '@testing-library/react'
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
  it('renders all KPI card labels (marketified)', () => {
    render(<KpiStrip metrics={baseMetrics} />)
    expect(screen.getByText('Mistakes Caught')).toBeInTheDocument()
    expect(screen.getByText('Time Saved')).toBeInTheDocument()
    expect(screen.getByText('Sessions to Graduate')).toBeInTheDocument()
    expect(screen.getByText('False Alarms')).toBeInTheDocument()
    expect(screen.getByText('Brain Footprint')).toBeInTheDocument()
  })

  it('shows "—" placeholder for null/zero values', () => {
    render(<KpiStrip metrics={baseMetrics} />)
    const dashes = screen.getAllByText('—')
    expect(dashes.length).toBeGreaterThanOrEqual(2)
  })

  it('renders destructive tone for False Alarms > 0', () => {
    const m: KpiMetrics = { ...baseMetrics, misfireCount: 2, totalFires: 10 }
    render(<KpiStrip metrics={m} />)
    const change = screen.getByText(/10 times your AI helped/)
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
  it('renders five cards with human labels', () => {
    render(<KpiStrip metrics={fullMetrics} />)
    expect(screen.getByText('Mistakes Caught')).toBeInTheDocument()
    expect(screen.getByText('Time Saved')).toBeInTheDocument()
    expect(screen.getByText('Sessions to Graduate')).toBeInTheDocument()
    expect(screen.getByText('False Alarms')).toBeInTheDocument()
    expect(screen.getByText('Brain Footprint')).toBeInTheDocument()
  })

  it('renders time saved as approximate hours when >= 60 min', () => {
    render(<KpiStrip metrics={fullMetrics} />)
    expect(screen.getByText('~1.6h')).toBeInTheDocument()
  })

  it('renders em dash for null WoW deltas', () => {
    render(<KpiStrip metrics={{ ...fullMetrics, correctionRateWoWDelta: null }} />)
    const card = screen.getByTestId(/kpi-mistakes-caught/)
    expect(within(card).getByText('—')).toBeInTheDocument()
  })

  it('includes plain-language tooltip copy on the Time Saved card', () => {
    render(<KpiStrip metrics={fullMetrics} />)
    const card = screen.getByTestId(/kpi-time-saved/)
    const tip = card.getAttribute('title') ?? ''
    expect(tip).toMatch(/3 minutes|correction|AI caught/)
  })
})
