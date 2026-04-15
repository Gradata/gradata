import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { GraduationProgressBar } from '@/components/brain/GraduationProgressBar'
import type { GraduationCounts } from '@/lib/analytics-client'

const counts: GraduationCounts = {
  instinct: 4,
  pattern: 3,
  rule: 1,
  totalActive: 4,
  avgConfidenceByState: { INSTINCT: 0.3, PATTERN: 0.62, RULE: 0.95 },
}

describe('GraduationProgressBar', () => {
  it('renders three tier segments via aria-label', () => {
    const { container } = render(<GraduationProgressBar counts={counts} />)
    expect(container.querySelector('[aria-label^="Watching"]')).toBeTruthy()
    expect(container.querySelector('[aria-label^="Learning"]')).toBeTruthy()
    expect(container.querySelector('[aria-label^="Graduated"]')).toBeTruthy()
  })

  it('shows the three human-readable tier labels', () => {
    render(<GraduationProgressBar counts={counts} />)
    expect(screen.getByText('Watching')).toBeInTheDocument()
    expect(screen.getByText('Learning')).toBeInTheDocument()
    expect(screen.getByText('Graduated')).toBeInTheDocument()
  })

  it('segment widths sum to 100% (or 0% when no lessons)', () => {
    const { container } = render(<GraduationProgressBar counts={counts} />)
    const segments = Array.from(
      container.querySelectorAll('[aria-label]'),
    ) as HTMLElement[]
    const total = segments.reduce(
      (s, el) => s + parseFloat(el.style.width),
      0,
    )
    expect(total).toBeCloseTo(100, 1)
  })

  it('handles zero-lesson case without NaN', () => {
    const empty: GraduationCounts = {
      instinct: 0,
      pattern: 0,
      rule: 0,
      totalActive: 0,
      avgConfidenceByState: { INSTINCT: 0, PATTERN: 0, RULE: 0 },
    }
    const { container } = render(<GraduationProgressBar counts={empty} />)
    const segments = Array.from(
      container.querySelectorAll('[aria-label]'),
    ) as HTMLElement[]
    segments.forEach((el) => expect(el.style.width).toBe('0%'))
  })

  it('shows total count summary', () => {
    render(<GraduationProgressBar counts={counts} />)
    expect(screen.getByText('8 total')).toBeInTheDocument()
  })
})
