'use client'

import { useState } from 'react'
import { GlassCard } from '@/components/layout/GlassCard'
import { Button } from '@/components/ui/button'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { ErrorState } from '@/components/shared/ErrorState'
import { useApi } from '@/hooks/useApi'
import type { UserProfile } from '@/types/api'
import api from '@/lib/api'
import { PlanBadge, PLANS, type PlanTier } from '@/components/brain/PlanBadge'

export default function SettingsPage() {
  const { data: profile, loading, error, refetch } = useApi<UserProfile>('/users/me')
  const [upgrading, setUpgrading] = useState<PlanTier | null>(null)
  const [upgradeError, setUpgradeError] = useState<string | null>(null)

  if (loading) return <LoadingSpinner className="py-20" />
  if (error) return <ErrorState message={error} onRetry={refetch} />
  if (!profile) return <ErrorState message="Could not load profile" />

  const memberSince = new Date(profile.created_at).toLocaleDateString('en-US', {
    year: 'numeric', month: 'long', day: 'numeric',
  })

  const currentPlan = (profile.plan?.toLowerCase() ?? 'free') as PlanTier

  const handleUpgrade = async (target: PlanTier) => {
    setUpgrading(target)
    setUpgradeError(null)
    try {
      const res = await api.post<{ checkout_url: string }>('/billing/checkout', {
        plan: target,
      })
      window.location.href = res.data.checkout_url
    } catch (err: any) {
      setUpgradeError(err?.response?.data?.detail ?? 'Could not start checkout. Try again.')
      setUpgrading(null)
    }
  }

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-[22px]">Settings</h1>
        <p className="mt-1 text-[13px] text-[var(--color-body)]">Manage your account and plan</p>
      </div>

      <GlassCard gradTop>
        <h3 className="mb-5 text-[15px] font-semibold">Profile</h3>
        <div className="space-y-3">
          <Row label="Display name" value={profile.display_name || 'Not set'} />
          <Row label="Email" value={profile.email || 'Not set'} />
          <Row label="Member since" value={memberSince} />
        </div>
      </GlassCard>

      <GlassCard gradTop>
        <div className="mb-5 flex items-baseline justify-between">
          <h3 className="text-[15px] font-semibold">Plan</h3>
          <PlanBadge tier={currentPlan} />
        </div>

        {upgradeError && (
          <div className="mb-4 rounded-[0.5rem] border border-[var(--color-destructive)]/30 bg-[var(--color-destructive)]/10 px-4 py-2.5 text-[13px] text-[var(--color-destructive)]">
            {upgradeError}
          </div>
        )}

        <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
          {(['free', 'cloud', 'team'] as const).map((tier) => {
            const plan = PLANS[tier]
            const isCurrent = tier === currentPlan
            const canUpgrade = PLANS[tier].rank > PLANS[currentPlan].rank
            return (
              <div
                key={tier}
                className={`relative rounded-[0.5rem] border p-4 transition-all ${
                  isCurrent
                    ? 'border-[var(--color-accent-blue)]/40 bg-[rgba(58,130,255,0.05)]'
                    : 'border-[var(--color-border)] bg-white/[0.02]'
                }`}
              >
                <div className="mb-2 flex items-baseline justify-between">
                  <div className="font-mono text-[10px] uppercase tracking-wider text-[var(--color-body)]">
                    {plan.name}
                  </div>
                  {isCurrent && (
                    <span className="rounded-[0.25rem] bg-[rgba(58,130,255,0.15)] px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-[var(--color-accent-blue)]">
                      current
                    </span>
                  )}
                </div>
                <div className="font-[var(--font-heading)] text-[24px] font-bold">
                  {plan.price}
                  {plan.priceUnit && <span className="text-[12px] font-normal text-[var(--color-body)]">{plan.priceUnit}</span>}
                </div>
                <ul className="mt-3 space-y-1.5 text-[11px] text-[var(--color-body)]">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-start gap-1.5">
                      <span className="mt-0.5 text-[var(--color-success)]">✓</span>
                      {f}
                    </li>
                  ))}
                </ul>
                <Button
                  variant={canUpgrade ? 'default' : 'outline'}
                  disabled={!canUpgrade || upgrading !== null}
                  className="mt-4 w-full"
                  onClick={() => canUpgrade && handleUpgrade(tier)}
                >
                  {upgrading === tier ? 'Redirecting…' : isCurrent ? 'Current' : canUpgrade ? 'Upgrade' : 'Downgrade'}
                </Button>
              </div>
            )
          })}
        </div>
      </GlassCard>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between border-b border-[var(--color-border)] pb-3 last:border-none last:pb-0">
      <span className="text-[13px] text-[var(--color-body)]">{label}</span>
      <span className="text-[13px]">{value}</span>
    </div>
  )
}
