import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PlanBadge, PlanGate, PLANS } from '@/components/brain/PlanBadge'

describe('PlanBadge', () => {
  it('renders the correct tier name for each plan', () => {
    const { rerender } = render(<PlanBadge tier="free" />)
    expect(screen.getByText('Free')).toBeInTheDocument()
    rerender(<PlanBadge tier="cloud" />)
    expect(screen.getByText('Cloud')).toBeInTheDocument()
    rerender(<PlanBadge tier="team" />)
    expect(screen.getByText('Team')).toBeInTheDocument()
    rerender(<PlanBadge tier="enterprise" />)
    expect(screen.getByText('Enterprise')).toBeInTheDocument()
  })

  it('applies the matching tone style class for each tier', () => {
    const cases: Array<[Parameters<typeof PlanBadge>[0]['tier'], string]> = [
      ['free', 'text-[var(--color-body)]'],
      ['cloud', 'text-[var(--color-accent-blue)]'],
      ['team', 'text-[var(--color-accent-violet)]'],
      ['enterprise', 'text-[var(--color-warning)]'],
    ]
    cases.forEach(([tier, klass]) => {
      const { unmount } = render(<PlanBadge tier={tier} />)
      const badge = screen.getByText(PLANS[tier].name)
      expect(badge.className).toContain(klass)
      unmount()
    })
  })
})

describe('PlanGate', () => {
  it('renders children when current rank meets the requirement', () => {
    render(
      <PlanGate current="team" requires="cloud" featureName="Trends">
        <div>secret content</div>
      </PlanGate>,
    )
    expect(screen.getByText('secret content')).toBeInTheDocument()
    // No upgrade overlay
    expect(screen.queryByText(/Upgrade to/)).not.toBeInTheDocument()
  })

  it('renders the upgrade overlay when current rank is below requirement', () => {
    render(
      <PlanGate current="free" requires="team" featureName="Leaderboard">
        <div>locked content</div>
      </PlanGate>,
    )
    // Overlay shows requirement
    expect(screen.getByText('Upgrade to Team')).toBeInTheDocument()
    expect(screen.getByText(/Leaderboard/)).toBeInTheDocument()
  })

  it('treats equal ranks as sufficient (current === requires)', () => {
    render(
      <PlanGate current="cloud" requires="cloud" featureName="Rules">
        <div>rules content</div>
      </PlanGate>,
    )
    expect(screen.queryByText(/Upgrade to/)).not.toBeInTheDocument()
  })
})
