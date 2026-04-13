import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { ClearDemoButton } from '@/components/brain/ClearDemoButton'

// Mock the api client so the component's network call is inspectable.
const postMock = vi.fn()
vi.mock('@/lib/api', () => ({
  default: {
    post: (...args: unknown[]) => postMock(...args),
  },
}))

// `useRouter` requires an AppRouter context at runtime; tests don't render one.
const pushMock = vi.fn()
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: pushMock, replace: vi.fn(), refresh: vi.fn() }),
}))

beforeEach(() => {
  postMock.mockReset()
  pushMock.mockReset()
})

describe('ClearDemoButton', () => {
  it('does not call the API until the dialog is confirmed', () => {
    render(<ClearDemoButton brainId="brain-1" />)
    // Open the trigger
    fireEvent.click(screen.getByRole('button', { name: /remove demo data/i }))
    // Dialog opens but no network call yet
    expect(postMock).not.toHaveBeenCalled()
  })

  it('posts to /brains/{id}/clear-demo on confirm', async () => {
    postMock.mockResolvedValue({ data: { deleted: 3, by_table: { lessons: 3 } } })

    const onCleared = vi.fn()
    render(<ClearDemoButton brainId="brain-42" onCleared={onCleared} />)

    // Open dialog
    fireEvent.click(screen.getByRole('button', { name: /remove demo data/i }))
    // There are now two matching buttons (trigger + confirm). The confirm is the
    // one inside the dialog footer — it's the last one.
    const buttons = screen.getAllByRole('button', { name: /remove demo data/i })
    fireEvent.click(buttons[buttons.length - 1])

    await waitFor(() => {
      expect(postMock).toHaveBeenCalledWith('/brains/brain-42/clear-demo')
    })
    await waitFor(() => {
      expect(onCleared).toHaveBeenCalledWith({ deleted: 3, by_table: { lessons: 3 } })
    })
    expect(screen.getByText(/Removed 3 demo rows/i)).toBeInTheDocument()
  })

  it('renders the success banner with correct singular copy', async () => {
    postMock.mockResolvedValue({ data: { deleted: 1, by_table: { lessons: 1 } } })
    render(<ClearDemoButton brainId="brain-1" />)

    fireEvent.click(screen.getByRole('button', { name: /remove demo data/i }))
    const buttons = screen.getAllByRole('button', { name: /remove demo data/i })
    fireEvent.click(buttons[buttons.length - 1])

    await waitFor(() => {
      expect(screen.getByText(/Removed 1 demo row\./)).toBeInTheDocument()
    })
  })

  it('shows an error banner when the API fails', async () => {
    postMock.mockRejectedValue(new Error('Server exploded'))
    render(<ClearDemoButton brainId="brain-1" />)

    fireEvent.click(screen.getByRole('button', { name: /remove demo data/i }))
    const buttons = screen.getAllByRole('button', { name: /remove demo data/i })
    fireEvent.click(buttons[buttons.length - 1])

    await waitFor(() => {
      expect(screen.getByText(/Server exploded/i)).toBeInTheDocument()
    })
  })
})
