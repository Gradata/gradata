import { PlanBadge, type PlanTier } from '@/components/brain/PlanBadge'
import type { AdminCustomer } from '@/types/api'
import { formatRelativeAgo } from '@/lib/format'

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
          {customer.last_active ? `last active ${formatRelativeAgo(customer.last_active)}` : 'never active'}
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

/**
 * True when a useApi error looks like a 403 from the operator allowlist.
 *
 * Prefers the structured HTTP status code from `useApi.errorStatus`. The
 * string-message fallback only matches the exact backend detail phrase set by
 * `require_operator` ("Operator access …"), so a 401 session error or an
 * unrelated 500 no longer misrenders as the friendly no-access state.
 */
export function isForbidden(
  error: { message: string | null; status: number | null } | string | null,
): boolean {
  if (!error) return false
  if (typeof error === 'string') {
    // Legacy string-only call sites: only match the exact backend detail.
    return error.startsWith('Operator access')
  }
  if (error.status === 403) return true
  if (error.status !== null) return false
  // Network-level failure with no status: match the exact backend detail.
  return error.message !== null && error.message.startsWith('Operator access')
}
