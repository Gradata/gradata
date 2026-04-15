import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PlanGate } from '@/components/brain/PlanBadge'

describe('PlanGate', () => {
  it('renders children when current plan meets required rank', () => {
    render(
      <PlanGate current="team" requires="cloud" featureName="Test">
        <div data-testid="child">child</div>
      </PlanGate>,
    )
    expect(screen.getByTestId('child')).toBeInTheDocument()
    expect(screen.queryByText(/Upgrade to/i)).not.toBeInTheDocument()
  })

  it('renders blur + upgrade CTA when current plan below required', () => {
    render(
      <PlanGate current="free" requires="cloud" featureName="Meta rules">
        <div data-testid="child">child</div>
      </PlanGate>,
    )
    expect(screen.getByText(/Upgrade to Cloud/i)).toBeInTheDocument()
    expect(screen.getByText(/Meta rules/i)).toBeInTheDocument()
  })

  it('bypasses gate when bypass=true even on free plan', () => {
    render(
      <PlanGate current="free" requires="team" featureName="Team analytics" bypass>
        <div data-testid="child">child</div>
      </PlanGate>,
    )
    expect(screen.getByTestId('child')).toBeInTheDocument()
    expect(screen.queryByText(/Upgrade to/i)).not.toBeInTheDocument()
  })

  it('gates normally when bypass=false on free plan', () => {
    render(
      <PlanGate current="free" requires="cloud" featureName="Meta rules" bypass={false}>
        <div data-testid="child">child</div>
      </PlanGate>,
    )
    expect(screen.getByText(/Upgrade to Cloud/i)).toBeInTheDocument()
  })
})
