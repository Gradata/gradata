'use client'

import { useState } from 'react'
import { GlassCard } from '@/components/layout/GlassCard'
import { Button } from '@/components/ui/button'
import { PlanBadge, PLANS, type PlanTier } from '@/components/brain/PlanBadge'
import { useApi } from '@/hooks/useApi'
import type { UserProfile } from '@/types/api'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import api from '@/lib/api'

interface SubscriptionResponse {
  plan: PlanTier
  status: 'active' | 'past_due' | 'canceled' | 'none'
  current_period_end: string | null
  cancel_at_period_end: boolean
  stripe_customer_portal_url?: string
}

export default function BillingPage() {
  const { data: profile, loading: loadingProfile } = useApi<UserProfile>('/users/me')
  const { data: sub, loading: loadingSub } = useApi<SubscriptionResponse>('/billing/subscription')
  const [loadingPortal, setLoadingPortal] = useState(false)
  const [portalError, setPortalError] = useState<string | null>(null)

  if (loadingProfile || loadingSub) return <LoadingSpinner className="py-20" />

  const currentPlan = (sub?.plan ?? (profile?.plan as PlanTier) ?? 'free') as PlanTier
  const planMeta = PLANS[currentPlan] ?? PLANS.free

  const handlePortal = async () => {
    if (sub?.stripe_customer_portal_url) {
      window.location.href = sub.stripe_customer_portal_url
      return
    }
    setLoadingPortal(true)
    setPortalError(null)
    try {
      const res = await api.post<{ url: string }>('/billing/portal')
      window.location.href = res.data.url
    } catch (err: any) {
      setPortalError(err?.response?.data?.detail ?? 'Could not open customer portal.')
      setLoadingPortal(false)
    }
  }

  const periodEnd = sub?.current_period_end
    ? new Date(sub.current_period_end).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
    : null

  return (
    <div className="max-w-3xl space-y-6">
      <header>
        <h1 className="text-[22px]">Billing</h1>
        <p className="mt-1 text-[13px] text-[var(--color-body)]">
          Plan, invoices, payment methods — powered by Stripe
        </p>
      </header>

      <GlassCard gradTop>
        <div className="mb-4 flex items-baseline justify-between">
          <h3 className="text-[15px] font-semibold">Current plan</h3>
          <PlanBadge tier={currentPlan} />
        </div>

        <div className="mb-5 flex items-baseline gap-3">
          <span className="font-[var(--font-heading)] text-[28px] font-bold tabular-nums">
            {planMeta.price}
          </span>
          {planMeta.priceUnit && (
            <span className="text-[13px] text-[var(--color-body)]">{planMeta.priceUnit}</span>
          )}
          {sub?.status === 'active' && periodEnd && (
            <span className="ml-auto font-mono text-[11px] text-[var(--color-body)]">
              {sub.cancel_at_period_end ? 'cancels' : 'renews'} {periodEnd}
            </span>
          )}
          {sub?.status === 'past_due' && (
            <span className="ml-auto rounded-[0.25rem] bg-[rgba(239,68,68,0.12)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--color-destructive)]">
              past due
            </span>
          )}
          {sub?.status === 'canceled' && (
            <span className="ml-auto font-mono text-[11px] text-[var(--color-body)]">canceled</span>
          )}
        </div>

        {portalError && (
          <div className="mb-4 rounded-[0.5rem] border border-[var(--color-destructive)]/30 bg-[var(--color-destructive)]/10 px-4 py-2.5 text-[13px] text-[var(--color-destructive)]">
            {portalError}
          </div>
        )}

        <div className="flex gap-3">
          <Button onClick={handlePortal} disabled={loadingPortal}>
            {loadingPortal ? 'Opening…' : 'Manage billing in Stripe'}
          </Button>
          {currentPlan !== 'team' && (
            <a href="/settings">
              <Button variant="outline">See upgrade options</Button>
            </a>
          )}
        </div>
      </GlassCard>

      <GlassCard gradTop>
        <h3 className="mb-4 text-[15px] font-semibold">What you get on {planMeta.name}</h3>
        <ul className="space-y-2 text-[13px]">
          {planMeta.features.map((f) => (
            <li key={f} className="flex items-start gap-2">
              <span className="mt-0.5 text-[var(--color-success)]">✓</span>
              <span>{f}</span>
            </li>
          ))}
        </ul>
      </GlassCard>
    </div>
  )
}
