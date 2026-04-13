import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ActiveRulesPanel } from '@/components/brain/ActiveRulesPanel'
import type { Lesson } from '@/types/api'

const mk = (
  id: string,
  state: Lesson['state'],
  confidence: number,
  fire_count = 0,
  description?: string,
): Lesson => ({
  id,
  brain_id: 'b1',
  description: description ?? `desc-${id}`,
  category: 'TONE',
  state,
  confidence,
  fire_count,
  created_at: new Date().toISOString(),
})

describe('ActiveRulesPanel', () => {
  it('hides raw confidence text (sim decision — implicit signal only)', () => {
    const lessons = [mk('r1', 'RULE', 0.95, 3)]
    const { container } = render(<ActiveRulesPanel lessons={lessons} />)
    // No "0.95" or "95%" should be rendered for the rule row
    expect(container.textContent).not.toMatch(/0\.95/)
    expect(container.textContent).not.toMatch(/95%/)
  })

  it('sorts rules by confidence descending', () => {
    const lessons = [
      mk('low', 'RULE', 0.50, 1, 'low-desc'),
      mk('high', 'RULE', 0.99, 1, 'high-desc'),
      mk('mid', 'RULE', 0.75, 1, 'mid-desc'),
    ]
    render(<ActiveRulesPanel lessons={lessons} />)
    const items = screen.getAllByText(/-desc/)
    expect(items[0].textContent).toBe('high-desc')
    expect(items[1].textContent).toBe('mid-desc')
    expect(items[2].textContent).toBe('low-desc')
  })

  it('filters out INSTINCT lessons (only RULE + PATTERN visible)', () => {
    const lessons = [
      mk('r1', 'RULE', 0.95, 0, 'rule-visible'),
      mk('p1', 'PATTERN', 0.65, 0, 'pattern-visible'),
      mk('i1', 'INSTINCT', 0.35, 0, 'instinct-hidden'),
    ]
    render(<ActiveRulesPanel lessons={lessons} />)
    expect(screen.getByText('rule-visible')).toBeInTheDocument()
    expect(screen.getByText('pattern-visible')).toBeInTheDocument()
    expect(screen.queryByText('instinct-hidden')).not.toBeInTheDocument()
  })

  it('shows empty-state copy when no graduated rules', () => {
    render(<ActiveRulesPanel lessons={[mk('i1', 'INSTINCT', 0.3)]} />)
    expect(
      screen.getByText(/No graduated rules yet/i),
    ).toBeInTheDocument()
  })
})
