'use client'

import { GlassCard } from '@/components/layout/GlassCard'
import { PlanBadge, type PlanTier } from '@/components/brain/PlanBadge'
import { useApi } from '@/hooks/useApi'
import type { UserProfile } from '@/types/api'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { mockGlobalKpis, mockCustomers, mockAlerts, type AdminCustomer } from '@/lib/fixtures/mock-operator'

/**
 * Operator panel — god-mode. TODO(backend): /api/v1/admin/* with is_staff
 * RLS policy. For now gated client-side on email domain.
 */
const OPERATOR_EMAIL_DOMAINS = ['gradata.ai', 'sprites.ai']

const HEALTH_STYLE: Record<AdminCustomer['health'], string> = {
  healthy:  'bg-[rgba(34,197,94,0.12)] text-[var(--color-success)]',
  'at-risk': 'bg-[rgba(234,179,8,0.12)] text-[var(--color-warning)]',
  churning: 'bg-[rgba(239,68,68,0.12)] text-[var(--color-destructive)]',
}

const ALERT_STYLE = {
  'churn-risk':     'border-[var(--color-warning)]/40 bg-[rgba(234,179,8,0.05)]',
  'failed-payment': 'border-[var(--color-destructive)]/40 bg-[rgba(239,68,68,0.05)]',
  'usage-spike':    'border-[var(--color-accent-blue)]/40 bg-[rgba(58,130,255,0.05)]',
} as const

export default function OperatorPage() {
  const { data: profile, loading } = useApi<UserProfile>('/users/me')
  if (loading) return <LoadingSpinner className="py-20" />

  const domain = profile?.email?.split('@')[1] ?? ''
  const isOperator = OPERATOR_EMAIL_DOMAINS.includes(domain)

  if (!isOperator) {
    return (
      <div className="py-12 text-center">
        <h1 className="text-[22px]">Operator</h1>
        <p className="mt-3 text-[13px] text-[var(--color-body)]">
          This surface is only visible to the Gradata team.
        </p>
      </div>
    )
  }

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
          god mode · {domain}
        </span>
      </header>

      {/* Global KPIs */}
      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi label="MRR" value={`$${mockGlobalKpis.mrr_usd.toLocaleString()}`}
             sub={`+${mockGlobalKpis.mrr_delta_pct.toFixed(1)}% MoM`}
             tone={mockGlobalKpis.mrr_delta_pct > 0 ? 'pos' : 'neg'} />
        <Kpi label="ARR" value={`$${mockGlobalKpis.arr_usd.toLocaleString()}`}
             sub="annual run rate" tone="neu" />
        <Kpi label="Churn (30d)"
             value={`${(mockGlobalKpis.churn_rate * 100).toFixed(1)}%`}
             sub={mockGlobalKpis.churn_rate < 0.05 ? 'below target 5%' : 'over target'}
             tone={mockGlobalKpis.churn_rate < 0.05 ? 'pos' : 'neg'} />
        <Kpi label="NRR" value={`${(mockGlobalKpis.net_revenue_retention * 100).toFixed(0)}%`}
             sub={mockGlobalKpis.net_revenue_retention >= 1.10 ? 'above target 110%' : 'below target'}
             tone={mockGlobalKpis.net_revenue_retention >= 1.10 ? 'pos' : 'neg'} />
      </div>

      {/* Alerts */}
      {mockAlerts.length > 0 && (
        <GlassCard gradTop className="mb-4">
          <h3 className="mb-4 text-[15px] font-semibold">Alerts</h3>
          <ul className="space-y-2">
            {mockAlerts.map((a) => (
              <li key={a.id} className={`rounded-[0.5rem] border p-3 ${ALERT_STYLE[a.kind]}`}>
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

      {/* Customer list */}
      <GlassCard gradTop>
        <div className="mb-5 flex items-baseline justify-between">
          <h3 className="text-[15px] font-semibold">Customers</h3>
          <span className="text-[12px] text-[var(--color-body)]">
            {mockGlobalKpis.customers_active}/{mockGlobalKpis.customers_total} active
          </span>
        </div>
        <ul className="divide-y divide-[var(--color-border)]">
          {mockCustomers.map((c) => (
            <li key={c.id} className="flex flex-wrap items-center gap-x-4 gap-y-3 py-3 first:pt-0 last:pb-0 sm:flex-nowrap">
              <div className="min-w-0 flex-1 basis-full sm:basis-auto">
                <div className="flex flex-wrap items-baseline gap-2.5">
                  <span className="text-[13px] font-medium">{c.company}</span>
                  <PlanBadge tier={c.plan as PlanTier} />
                  <span className={`rounded-[0.25rem] px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wider ${HEALTH_STYLE[c.health]}`}>
                    {c.health}
                  </span>
                </div>
                <div className="font-mono text-[10px] text-[var(--color-body)]">
                  last active {formatAgo(c.last_active)}
                </div>
              </div>
              <div className="flex-1 sm:w-24 sm:flex-none sm:text-right">
                <div className="font-mono text-[13px] tabular-nums">${c.mrr_usd}</div>
                <div className="font-mono text-[10px] text-[var(--color-body)]">MRR</div>
              </div>
              <div className="flex-1 sm:w-20 sm:flex-none sm:text-right">
                <div className="font-mono text-[13px] tabular-nums">{c.active_users}</div>
                <div className="font-mono text-[10px] text-[var(--color-body)]">users</div>
              </div>
              <div className="flex-1 sm:w-20 sm:flex-none sm:text-right">
                <div className="font-mono text-[13px] tabular-nums">{c.brains}</div>
                <div className="font-mono text-[10px] text-[var(--color-body)]">brains</div>
              </div>
            </li>
          ))}
        </ul>
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
  const h = Math.floor(diffMs / 3600_000)
  if (h < 1) return 'just now'
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}
