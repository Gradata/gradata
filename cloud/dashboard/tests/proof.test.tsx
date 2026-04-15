import { describe, it, expect, vi } from 'vitest'
import { render } from '@testing-library/react'

// Mock ABProofPanel's api dependency so it renders without network
vi.mock('@/lib/api', () => ({
  default: { get: vi.fn().mockResolvedValue({ data: { available: false } }) },
}))

import ProofPage from '../app/(dashboard)/proof/page'

describe('/proof page', () => {
  it('renders without crashing', () => {
    const { container } = render(<ProofPage />)
    expect(container.firstChild).not.toBeNull()
  })

  it('contains the word "proof" somewhere in the heading', () => {
    const { getAllByText } = render(<ProofPage />)
    expect(getAllByText(/proof/i).length).toBeGreaterThan(0)
  })
})
