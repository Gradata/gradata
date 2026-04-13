import { PlanBadge, type PlanTier } from '@/components/brain/PlanBadge'
import type { AdminCustomer } from '@/types/api'

const HEALTH_STYLE: Record<AdminCustomer['health'], string> = {
  healthy:   'bg-[rgba(34,197,94,0.12)] text-[var(--color-success)]',
  'at-risk': 'bg-[rgba(234,179,8,0.12)] text-[var(--color-warning)]',
  churning:  'bg-[rgba(239,68,68,0.12)] text-[var(--color-destructive)]',
}

export function CustomerRow({ customer }: { customer: AdminCustomer }) {
  const tier = (customer.plan === 'pro' ? 'cloud' : customer.plan) as PlanTier
  return (
    <li
      data-testid="operator-customer"
      className="flex flex-wrap items-center gap-x-4 gap-y-3 py-3 first:pt-0 last:pb-0 sm:flex-nowrap"
    >
      <div className="min-w-0 flex-1 basis-full sm:basis-auto">
        <div className="flex flex-wrap items-baseline gap-2.5">
          <span className="text-[13px] font-medium">{customer.company}</span>
          <PlanBadge tier={tier} />
          <span
            className={`rounded-[0.25rem] px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wider ${
              HEALTH_STYLE[customer.health] ?? ''
            }`}
          >
            {customer.health}
          </span>
        </div>
        <div className="font-mono text-[10px] text-[var(--color-body)]">
          {customer.last_active ? `last active ${formatAgo(customer.last_active)}` : 'never active'}
        </div>
      </div>
      <div className="flex-1 sm:w-24 sm:flex-none sm:text-right">
        <div className="font-mono text-[13px] tabular-nums">${customer.mrr_usd}</div>
        <div className="font-mono text-[10px] text-[var(--color-body)]">MRR</div>
      </div>
      <div className="flex-1 sm:w-20 sm:flex-none sm:text-right">
        <div className="font-mono text-[13px] tabular-nums">{customer.active_users}</div>
        <div className="font-mono text-[10px] text-[var(--color-body)]">users</div>
      </div>
      <div className="flex-1 sm:w-20 sm:flex-none sm:text-right">
        <div className="font-mono text-[13px] tabular-nums">{customer.brains}</div>
        <div className="font-mono text-[10px] text-[var(--color-body)]">brains</div>
      </div>
    </li>
  )
}

function formatAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime()
  if (Number.isNaN(diffMs)) return '—'
  const h = Math.floor(diffMs / 3600_000)
  if (h < 1) return 'just now'
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

/**
 * True when a useApi error string looks like a 403 from the operator allowlist.
 * `useApi` only exposes the detail string so we pattern-match; the backend's
 * `require_operator` uses "Operator access …" detail messages.
 */
export function isForbidden(errorMessage: string | null): boolean {
  if (!errorMessage) return false
  const lower = errorMessage.toLowerCase()
  return (
    lower.includes('forbidden') ||
    lower.includes('not authorized') ||
    lower.includes('operator') ||
    lower.includes('status code 403')
  )
}
