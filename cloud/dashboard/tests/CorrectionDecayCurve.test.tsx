import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { CorrectionDecayCurve } from '@/components/brain/CorrectionDecayCurve'
import type { Lesson, Correction } from '@/types/api'

const daysAgo = (n: number) => new Date(Date.now() - n * 86_400_000).toISOString()

const mkLesson = (id: string, graduated_at: string): Lesson => ({
  id,
  brain_id: 'b1',
  description: id,
  category: 'TONE',
  state: 'RULE',
  confidence: 0.9,
  fire_count: 0,
  created_at: daysAgo(60),
  graduated_at,
} as Lesson)

const mkCorr = (id: string, daysAgoN: number): Correction => ({
  id,
  brain_id: 'b1',
  severity: 'minor',
  category: 'TONE',
  description: 'x',
  draft_preview: null,
  final_preview: null,
  created_at: daysAgo(daysAgoN),
})

describe('CorrectionDecayCurve graduation markers', () => {
  it('renders a marker for each graduated rule in range', () => {
    const corrections = Array.from({ length: 10 }, (_, i) => mkCorr(`c${i}`, i + 1))
    const lessons = [
      mkLesson('a', daysAgo(3)),
      mkLesson('b', daysAgo(5)),
    ]
    const { container } = render(
      <CorrectionDecayCurve corrections={corrections} lessons={lessons} range="7d" />,
    )
    const markers = container.querySelectorAll('[data-graduation-marker]')
    expect(markers.length).toBe(2)
  })

  it('caps markers at 12 and renders "+N more" note', () => {
    const corrections = Array.from({ length: 30 }, (_, i) => mkCorr(`c${i}`, i + 1))
    const lessons = Array.from({ length: 15 }, (_, i) => mkLesson(`r${i}`, daysAgo(i + 1)))
    const { container, getByText } = render(
      <CorrectionDecayCurve corrections={corrections} lessons={lessons} range="30d" />,
    )
    const markers = container.querySelectorAll('[data-graduation-marker]')
    expect(markers.length).toBe(12)
    expect(getByText(/\+3 more/i)).toBeInTheDocument()
  })
})
