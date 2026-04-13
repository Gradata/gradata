'use client'

import { GlassCard } from '@/components/layout/GlassCard'
import { useApi } from '@/hooks/useApi'
import type {
  AdminAlert,
  AdminCustomer,
  AdminGlobalKpis,
  UserProfile,
} from '@/types/api'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { ErrorState } from '@/components/shared/ErrorState'
import { CustomerRow, isForbidden } from '@/components/operator/CustomerRow'

/**
 * Operator panel — god-mode. Backend enforces the @gradata.ai / @sprites.ai
 * allowlist via `require_operator`; on forbidden we render a friendly empty
 * state instead of surfacing a raw 403.
 */
const ALERT_STYLE: Record<string, string> = {
  'churn-risk':     'border-[var(--color-warning)]/40 bg-[rgba(234,179,8,0.05)]',
  'failed-payment': 'border-[var(--color-destructive)]/40 bg-[rgba(239,68,68,0.05)]',
  'usage-spike':    'border-[var(--color-accent-blue)]/40 bg-[rgba(58,130,255,0.05)]',
}

export default function OperatorPage() {
  const { data: profile, loading: profileLoading } = useApi<UserProfile>('/users/me')

  const {
    data: kpis,
    loading: kpisLoading,
    error: kpisError,
    errorStatus: kpisStatus,
    refetch: refetchKpis,
  } = useApi<AdminGlobalKpis>('/admin/global-kpis')
  const {
    data: customers,
    loading: customersLoading,
    error: customersError,
    errorStatus: customersStatus,
    refetch: refetchCustomers,
  } = useApi<AdminCustomer[]>('/admin/customers')
  const {
    data: alerts,
    loading: alertsLoading,
    error: alertsError,
    errorStatus: alertsStatus,
    refetch: refetchAlerts,
  } = useApi<AdminAlert[]>('/admin/alerts')

  if (profileLoading) return <LoadingSpinner className="py-20" />

  // The backend is the source of truth for operator access, but we surface
  // a friendlier screen when it returns 403 rather than the raw error.
  const blocked =
    isForbidden({ message: kpisError, status: kpisStatus }) ||
    isForbidden({ message: customersError, status: customersStatus }) ||
    isForbidden({ message: alertsError, status: alertsStatus })

  if (blocked) {
    return (
      <div className="py-12 text-center">
        <h1 className="text-[22px]">Operator</h1>
        <p className="mt-3 text-[13px] text-[var(--color-body)]">
          This surface is only visible to the Gradata team.
        </p>
      </div>
    )
  }

  if (kpisLoading || customersLoading || alertsLoading) {
    return <LoadingSpinner className="py-20" />
  }

  // Any non-403 fetch failure should surface as a retryable error instead of
  // falling through to an empty customer/alert list.
  const loadError = kpisError || customersError || alertsError
  if (loadError) {
    return (
      <ErrorState
        message={loadError}
        onRetry={() => {
          refetchKpis()
          refetchCustomers()
          refetchAlerts()
        }}
      />
    )
  }

  const customerRows = customers ?? []
  const alertRows = alerts ?? []
  const k = kpis
  const domain = profile?.email?.split('@')[1] ?? ''

  return (
    <>
      <header className="mb-7 flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h1 className="text-[22px]">Operator</h1>
          <p className="mt-1 text-[13px] text-[var(--color-body)]">
            Customer fleet overview
          </p>
        </div>
        <span className="font-mono text-[11px] uppercase tracking-wider text-[var(--color-accent-violet)]">
          god mode{domain ? ` · ${domain}` : ''}
        </span>
      </header>

      {k && (
        <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Kpi label="MRR" value={`$${k.mrr_usd.toLocaleString()}`}
               sub={`${k.mrr_delta_pct >= 0 ? '+' : ''}${k.mrr_delta_pct.toFixed(1)}% MoM`}
               tone={k.mrr_delta_pct >= 0 ? 'pos' : 'neg'} />
          <Kpi label="ARR" value={`$${k.arr_usd.toLocaleString()}`} sub="annual run rate" tone="neu" />
          <Kpi label="Churn (30d)"
               value={`${(k.churn_rate * 100).toFixed(1)}%`}
               sub={k.churn_rate < 0.05 ? 'below target 5%' : 'over target'}
               tone={k.churn_rate < 0.05 ? 'pos' : 'neg'} />
          <Kpi label="NRR" value={`${(k.net_revenue_retention * 100).toFixed(0)}%`}
               sub={k.net_revenue_retention >= 1.10 ? 'above target 110%' : 'below target'}
               tone={k.net_revenue_retention >= 1.10 ? 'pos' : 'neg'} />
        </div>
      )}

      {alertRows.length > 0 && (
        <GlassCard gradTop className="mb-4">
          <h3 className="mb-4 text-[15px] font-semibold">Alerts</h3>
          <ul className="space-y-2">
            {alertRows.map((a) => (
              <li
                key={a.id}
                data-testid="operator-alert"
                className={`rounded-[0.5rem] border p-3 ${ALERT_STYLE[a.kind] ?? 'border-[var(--color-border)]'}`}
              >
                <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                  <div className="min-w-0 flex-1">
                    <span className="font-mono text-[10px] uppercase tracking-wider">
                      {a.kind.replace('-', ' ')}
                    </span>
                    <span className="ml-3 text-[13px] font-medium">{a.customer}</span>
                    <span className="ml-2 text-[13px] text-[var(--color-body)]">· {a.detail}</span>
                  </div>
                  <span className="font-mono text-[10px] text-[var(--color-body)] shrink-0">
                    {formatAgo(a.created_at)}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </GlassCard>
      )}

      <GlassCard gradTop>
        <div className="mb-5 flex items-baseline justify-between">
          <h3 className="text-[15px] font-semibold">Customers</h3>
          {k && (
            <span className="text-[12px] text-[var(--color-body)]">
              {k.customers_active}/{k.customers_total} active
            </span>
          )}
        </div>
        {customerRows.length === 0 ? (
          <p className="py-6 text-center text-[13px] text-[var(--color-body)]">No customers yet.</p>
        ) : (
          <ul className="divide-y divide-[var(--color-border)]">
            {customerRows.map((c) => <CustomerRow key={c.id} customer={c} />)}
          </ul>
        )}
      </GlassCard>
    </>
  )
}

function Kpi({ label, value, sub, tone }: {
  label: string; value: string; sub: string; tone: 'pos' | 'neg' | 'neu'
}) {
  return (
    <GlassCard className="p-5">
      <div className="mb-2 text-[12px] font-medium text-[var(--color-body)]">{label}</div>
      <div className="font-[var(--font-heading)] text-[22px] sm:text-[28px] font-bold tabular-nums text-gradient-brand break-words">
        {value}
      </div>
      <div className={`mt-1 text-[12px] font-medium ${
        tone === 'pos' ? 'text-[var(--color-success)]'
          : tone === 'neg' ? 'text-[var(--color-destructive)]'
            : 'text-[var(--color-accent-blue)]'
      }`}>
        {sub}
      </div>
    </GlassCard>
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

