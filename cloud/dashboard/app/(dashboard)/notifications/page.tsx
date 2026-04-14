'use client'

import { useEffect, useState } from 'react'
import { GlassCard } from '@/components/layout/GlassCard'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { useApi } from '@/hooks/useApi'
import api from '@/lib/api'

/**
 * Notification preferences per SIM16 validation:
 * - Alerts: real-time (Slack/email) — correction spikes, rule regressions
 * - Digest: weekly email (default, configurable) — learning velocity summary
 * - In-app: dashboard bell — unread insights
 *
 * Weekly cadence intentional (not daily) — SIM16 rejected daily-check design.
 */
type DigestCadence = 'daily' | 'weekly' | 'monthly' | 'off'

interface Toggles {
  alert_correction_spike: boolean
  alert_rule_regression: boolean
  alert_meta_rule_emerged: boolean
  digest_cadence: DigestCadence
  digest_email: string
  slack_webhook: string
}

const DEFAULTS: Toggles = {
  alert_correction_spike: true,
  alert_rule_regression: true,
  alert_meta_rule_emerged: false,
  digest_cadence: 'weekly',
  digest_email: '',
  slack_webhook: '',
}

export default function NotificationsPage() {
  const { data: serverPrefs, loading } = useApi<Toggles>('/users/me/notifications')
  const [toggles, setToggles] = useState<Toggles>(DEFAULTS)
  const [saved, setSaved] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  useEffect(() => {
    if (serverPrefs) setToggles(serverPrefs)
  }, [serverPrefs])

  if (loading) return <LoadingSpinner className="py-20" />

  const handleSave = async () => {
    setSaving(true)
    setSaveError(null)
    try {
      const res = await api.put<Toggles>('/users/me/notifications', toggles)
      setToggles(res.data)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err: any) {
      setSaveError(err?.response?.data?.detail ?? 'Could not save preferences')
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <header className="mb-7">
        <h1 className="text-[22px]">Notifications</h1>
        <p className="mt-1 text-[13px] text-[var(--color-body)]">
          How we&apos;ll reach you — weekly digest by default, alerts only when it matters
        </p>
      </header>

      <div className="max-w-3xl space-y-6">
        <GlassCard gradTop>
          <h3 className="mb-4 text-[15px] font-semibold">Real-time alerts</h3>
          <div className="space-y-3">
            <ToggleRow
              label="Correction rate spike"
              description="If corrections jump more than 50% week-over-week"
              checked={toggles.alert_correction_spike}
              onChange={(v) => setToggles((t) => ({ ...t, alert_correction_spike: v }))}
            />
            <ToggleRow
              label="Rule regression"
              description="When a graduated rule misfires or recurs"
              checked={toggles.alert_rule_regression}
              onChange={(v) => setToggles((t) => ({ ...t, alert_rule_regression: v }))}
            />
            <ToggleRow
              label="New meta-rule emerged"
              description="A universal principle crystallized from 3+ rules"
              checked={toggles.alert_meta_rule_emerged}
              onChange={(v) => setToggles((t) => ({ ...t, alert_meta_rule_emerged: v }))}
            />
          </div>
        </GlassCard>

        <GlassCard gradTop>
          <h3 className="mb-4 text-[15px] font-semibold">Digest</h3>
          <p className="mb-4 text-[12px] text-[var(--color-body)]">
            Learning velocity summary: new graduated rules, correction trend, one insight.
            Weekly by default (SIM16-validated cadence).
          </p>
          <div className="mb-4 space-y-2">
            <Label htmlFor="cadence">Cadence</Label>
            <select
              id="cadence"
              value={toggles.digest_cadence}
              onChange={(e) => setToggles((t) => ({ ...t, digest_cadence: e.target.value as DigestCadence }))}
              className="w-full rounded-[0.5rem] border border-[var(--color-border)] bg-[rgba(21,29,48,0.6)] px-3 py-2 text-sm"
            >
              <option value="daily">Daily (not recommended)</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
              <option value="off">Off</option>
            </select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="email">Email (leave blank to use account email)</Label>
            <Input id="email" type="email" placeholder="digest@company.com"
              value={toggles.digest_email}
              onChange={(e) => setToggles((t) => ({ ...t, digest_email: e.target.value }))} />
          </div>
        </GlassCard>

        <GlassCard gradTop>
          <h3 className="mb-4 text-[15px] font-semibold">Slack</h3>
          <p className="mb-4 text-[12px] text-[var(--color-body)]">
            Post real-time alerts to a Slack channel via Incoming Webhook URL.
          </p>
          <div className="space-y-2">
            <Label htmlFor="slack">Webhook URL</Label>
            <Input id="slack" type="url"
              placeholder="https://hooks.slack.com/services/..."
              value={toggles.slack_webhook}
              onChange={(e) => setToggles((t) => ({ ...t, slack_webhook: e.target.value }))} />
          </div>
        </GlassCard>

        <div className="flex items-center justify-end gap-3">
          {saveError && (
            <span className="font-mono text-[11px] text-[var(--color-destructive)]">
              {saveError}
            </span>
          )}
          {saved && (
            <span className="font-mono text-[11px] text-[var(--color-success)]">
              ✓ preferences saved
            </span>
          )}
          <Button onClick={handleSave} disabled={saving}>
            {saving ? 'Saving…' : 'Save preferences'}
          </Button>
        </div>
      </div>
    </>
  )
}

function ToggleRow({ label, description, checked, onChange }: {
  label: string; description: string; checked: boolean; onChange: (v: boolean) => void
}) {
  return (
    <label className="flex items-start gap-3 cursor-pointer rounded-[0.5rem] p-3 -mx-3 transition-colors hover:bg-white/[0.02]">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-1 h-4 w-4 shrink-0 accent-[var(--color-accent-blue)]"
      />
      <div className="flex-1">
        <div className="text-[13px] font-medium">{label}</div>
        <div className="text-[12px] text-[var(--color-body)]">{description}</div>
      </div>
    </label>
  )
}
