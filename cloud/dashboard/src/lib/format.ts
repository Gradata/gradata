/**
 * Format an ISO timestamp as a coarse "X ago" string.
 * `fallback` is returned when the timestamp is null/invalid.
 */
export function formatRelativeAgo(
  iso: string | null | undefined,
  fallback: string = '—',
  now: number = Date.now(),
): string {
  if (!iso) return fallback
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return fallback
  const diffMs = now - t
  if (diffMs < 0) return 'just now'
  const mins = Math.floor(diffMs / 60_000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}
