import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { CustomerRow, isForbidden } from '@/components/operator/CustomerRow'
import type { AdminCustomer } from '@/types/api'

const mk = (over: Partial<AdminCustomer> = {}): AdminCustomer => ({
  id: over.id ?? 'c1',
  company: over.company ?? 'Acme',
  plan: over.plan ?? 'team',
  mrr_usd: over.mrr_usd ?? 99,
  active_users: over.active_users ?? 3,
  brains: over.brains ?? 3,
  last_active: 'last_active' in over ? over.last_active ?? null : new Date().toISOString(),
  health: over.health ?? 'healthy',
})

const wrap = (children: React.ReactNode) => (
  <ul>{children}</ul>
)

describe('CustomerRow', () => {
  it('renders company + plan + health for each customer', () => {
    render(wrap(<CustomerRow customer={mk({ company: 'Stripe', plan: 'team', health: 'healthy' })} />))
    expect(screen.getByText('Stripe')).toBeInTheDocument()
    expect(screen.getByText('healthy')).toBeInTheDocument()
  })

  it('shows "never active" when last_active is null', () => {
    render(wrap(<CustomerRow customer={mk({ last_active: null })} />))
    expect(screen.getByText(/never active/i)).toBeInTheDocument()
  })

  it('renders a plan badge (maps "pro" → "cloud")', () => {
    render(wrap(<CustomerRow customer={mk({ plan: 'pro' })} />))
    // PlanBadge should show "Cloud" for the pro → cloud mapping.
    expect(screen.getByText('Cloud')).toBeInTheDocument()
  })

  it('renders MRR, users, brains counts', () => {
    render(wrap(<CustomerRow customer={mk({ mrr_usd: 42, active_users: 7, brains: 9 })} />))
    expect(screen.getByText('$42')).toBeInTheDocument()
    expect(screen.getByText('7')).toBeInTheDocument()
    expect(screen.getByText('9')).toBeInTheDocument()
  })

  it('styles churning customers distinctly from healthy', () => {
    const { container } = render(wrap(<CustomerRow customer={mk({ health: 'churning' })} />))
    expect(container.innerHTML).toMatch(/destructive/)
  })
})

describe('isForbidden', () => {
  it('returns false for null', () => {
    expect(isForbidden(null)).toBe(false)
  })

  it('matches the FastAPI 403 detail string', () => {
    expect(isForbidden('Operator access denied')).toBe(true)
    expect(isForbidden('Operator access requires a verified email')).toBe(true)
  })

  it('matches a generic forbidden string', () => {
    expect(isForbidden('Request failed with status code 403')).toBe(true)
    expect(isForbidden('Forbidden')).toBe(true)
  })

  it('returns false for unrelated errors', () => {
    expect(isForbidden('Network Error')).toBe(false)
    expect(isForbidden('Not found')).toBe(false)
  })
})
