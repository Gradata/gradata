import axios from 'axios'

/** Extract a user-facing message from an axios/generic error. */
export function readApiError(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: string } | undefined)?.detail
    return detail || err.message || fallback
  }
  if (err instanceof Error) return err.message
  return fallback
}
