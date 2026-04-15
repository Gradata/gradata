import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ActiveRulesPanel } from '@/components/brain/ActiveRulesPanel'
import type { Lesson } from '@/types/api'

const daysAgo = (n: number) => new Date(Date.now() - n * 86_400_000).toISOString()

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

const mkRule = (
  id: string,
  opts: Partial<Lesson> & { graduated_at?: string; last_recurrence_at?: string } = {},
): Lesson => ({
  id,
  brain_id: 'b1',
  description: id,
  category: 'TONE',
  state: 'RULE',
  confidence: 0.9,
  fire_count: 0,
  created_at: daysAgo(60),
  ...opts,
} as Lesson)

describe('ActiveRulesPanel', () => {
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

  it('shows empty-state copy when nothing has graduated', () => {
    render(<ActiveRulesPanel lessons={[mk('i1', 'INSTINCT', 0.3)]} />)
    expect(
      screen.getByText(/Nothing graduated yet/i),
    ).toBeInTheDocument()
  })
})

describe('ActiveRulesPanel status glyphs', () => {
  it('renders filled dot + "N days holding" for rules clean >= 7 days', () => {
    const rules = [mkRule('a', { graduated_at: daysAgo(21) })]
    render(<ActiveRulesPanel lessons={rules} />)
    expect(screen.getByText(/21 days holding/i)).toBeInTheDocument()
    expect(document.querySelector('[data-glyph="clean-durable"]')).toBeInTheDocument()
  })

  it('renders open dot for clean < 7 days', () => {
    const rules = [mkRule('a', { graduated_at: daysAgo(3) })]
    render(<ActiveRulesPanel lessons={rules} />)
    expect(screen.getByText(/3 days holding/i)).toBeInTheDocument()
    expect(document.querySelector('[data-glyph="clean-new"]')).toBeInTheDocument()
  })

  it('renders half dot + "slipped Nd ago" for recurrence < 7 days', () => {
    const rules = [mkRule('a', { graduated_at: daysAgo(30), last_recurrence_at: daysAgo(2) })]
    render(<ActiveRulesPanel lessons={rules} />)
    expect(screen.getByText(/slipped 2d ago/i)).toBeInTheDocument()
    expect(document.querySelector('[data-glyph="recurred"]')).toBeInTheDocument()
  })

  it('renders "just learned" when streak data is absent', () => {
    const rules = [mkRule('a')]
    render(<ActiveRulesPanel lessons={rules} />)
    const row = screen.getByText('a').closest('li')!
    expect(row.textContent).toMatch(/just learned/i)
  })

  it('renders a "See all your rules" link to /rules', () => {
    render(<ActiveRulesPanel lessons={[]} />)
    const link = screen.getByRole('link', { name: /see all your rules/i })
    expect(link).toHaveAttribute('href', '/rules')
  })

  it('caps display at 8 rules', () => {
    const rules = Array.from({ length: 12 }, (_, i) => mkRule(`r${i}`, { graduated_at: daysAgo(i + 1) }))
    render(<ActiveRulesPanel lessons={rules} />)
    expect(document.querySelectorAll('[data-rule-row]').length).toBe(8)
  })
})
