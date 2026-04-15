import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { CategoriesChart } from '@/components/brain/CategoriesChart'
import type { BrainAnalytics } from '@/types/api'

const mkAnalytics = (
  corrections_by_category: Record<string, number>,
): BrainAnalytics => ({
  total_lessons: 0,
  total_corrections: 0,
  graduation_rate: 0,
  avg_confidence: 0,
  lessons_by_state: {},
  corrections_by_severity: {},
  corrections_by_category,
})

const DIMENSIONS = [
  'Goal Alignment',
  'Factual Integrity',
  'Clarity & Structure',
  'Domain Fit',
  'Tone & Register',
  'Actionability',
]

describe('CategoriesChart', () => {
  it('renders all 6 dimensions when classifier is healthy (>= 70% categorized)', () => {
    // Seed enough categorized data to pass the classifier-health gate so the
    // chart (not the still figuring out empty state) is rendered.
    render(<CategoriesChart analytics={mkAnalytics({ TONE: 1 })} />)
    DIMENSIONS.forEach((d) => {
      expect(screen.getByText(d)).toBeInTheDocument()
    })
  })

  it('folds legacy TONE → Tone & Register', () => {
    render(<CategoriesChart analytics={mkAnalytics({ TONE: 5 })} />)
    // The Tone & Register row count should be 5
    const toneLabel = screen.getByText('Tone & Register')
    const row = toneLabel.closest('li')
    expect(row?.textContent).toContain('5')
  })

  it('folds PROCESS → Actionability and ACCURACY → Factual Integrity', () => {
    render(
      <CategoriesChart
        analytics={mkAnalytics({ PROCESS: 4, ACCURACY: 7 })}
      />,
    )
    const action = screen.getByText('Actionability').closest('li')
    expect(action?.textContent).toContain('4')
    const fact = screen.getByText('Factual Integrity').closest('li')
    expect(fact?.textContent).toContain('7')
  })

  it('folds DRAFTING + FORMAT both into Clarity & Structure (sums)', () => {
    render(
      <CategoriesChart
        analytics={mkAnalytics({ DRAFTING: 3, FORMAT: 2 })}
      />,
    )
    const clarity = screen.getByText('Clarity & Structure').closest('li')
    expect(clarity?.textContent).toContain('5')
  })

  it('routes unknown categories to Factual Integrity (safe default)', () => {
    render(<CategoriesChart analytics={mkAnalytics({ UNKNOWN_THING: 9 })} />)
    const fact = screen.getByText('Factual Integrity').closest('li')
    expect(fact?.textContent).toContain('9')
  })
})

describe('CategoriesChart classifier health', () => {
  it('renders recalibration empty state when < 70% corrections are categorized', () => {
    // 3 OTHER + 1 TONE = 25% categorized
    render(
      <CategoriesChart
        analytics={mkAnalytics({ OTHER: 3, TONE: 1 })}
      />,
    )
    expect(screen.getByText(/still figuring out/i)).toBeInTheDocument()
  })

  it('renders the chart when >= 70% corrections have a real category', () => {
    // 3 TONE + 1 ACCURACY + 1 OTHER = 80% categorized
    render(
      <CategoriesChart
        analytics={mkAnalytics({ TONE: 3, ACCURACY: 1, OTHER: 1 })}
      />,
    )
    expect(screen.queryByText(/still figuring out/i)).not.toBeInTheDocument()
  })

  it('renders empty state when no corrections at all', () => {
    render(<CategoriesChart analytics={mkAnalytics({})} />)
    expect(screen.getByText(/still figuring out|no corrections/i)).toBeInTheDocument()
  })
})
