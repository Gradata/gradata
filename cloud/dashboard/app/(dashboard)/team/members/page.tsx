'use client'

import { useState } from 'react'
import { GlassCard } from '@/components/layout/GlassCard'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from '@/components/ui/dialog'
import { PlanGate, type PlanTier } from '@/components/brain/PlanBadge'
import { useApi } from '@/hooks/useApi'
import type { UserProfile } from '@/types/api'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { mockTeam, type MemberRole } from '@/lib/fixtures/mock-team'

const ROLE_BADGE: Record<MemberRole, string> = {
  owner:  'bg-[rgba(124,58,237,0.12)] text-[var(--color-accent-violet)]',
  admin:  'bg-[rgba(58,130,255,0.12)] text-[var(--color-accent-blue)]',
  member: 'bg-white/[0.06] text-[var(--color-body)]',
}

export default function TeamMembersPage() {
  const { data: profile, loading } = useApi<UserProfile>('/users/me')
  const [inviteOpen, setInviteOpen] = useState(false)
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState<MemberRole>('member')
  const [inviting, setInviting] = useState(false)
  const [inviteStatus, setInviteStatus] = useState<string | null>(null)

  if (loading) return <LoadingSpinner className="py-20" />

  const currentPlan = (profile?.plan?.toLowerCase() ?? 'free') as PlanTier

  const handleInvite = async () => {
    setInviting(true)
    setInviteStatus(null)
    // TODO(backend): POST /workspaces/{id}/invites — fake for now
    await new Promise((r) => setTimeout(r, 600))
    setInviteStatus(`Invite sent to ${inviteEmail}`)
    setInviteEmail('')
    setInviting(false)
  }

  return (
    <>
      <header className="mb-7 flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h1 className="text-[22px]">Members</h1>
          <p className="mt-1 text-[13px] text-[var(--color-body)]">
            Invite teammates and manage roles
          </p>
        </div>
        <Button onClick={() => setInviteOpen(true)}>Invite member</Button>
      </header>

      <PlanGate current={currentPlan} requires="team" featureName="Team member management">
        <GlassCard gradTop>
          <ul className="divide-y divide-[var(--color-border)]">
            {mockTeam.map((m) => (
              <li key={m.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 py-3 first:pt-0 last:pb-0 sm:flex-nowrap">
                <div className="min-w-0 flex-1 basis-full sm:basis-auto">
                  <div className="flex flex-wrap items-baseline gap-2.5">
                    <span className="text-[13px] font-medium">{m.name}</span>
                    <span className={`rounded-[0.25rem] px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wider ${ROLE_BADGE[m.role]}`}>
                      {m.role}
                    </span>
                    {m.status === 'inactive' && (
                      <span className="font-mono text-[10px] text-[var(--color-warning)]">inactive</span>
                    )}
                  </div>
                  <div className="font-mono text-[10px] text-[var(--color-body)] truncate">{m.email}</div>
                </div>
                <div className="font-mono text-[11px] text-[var(--color-body)] sm:w-32 sm:text-right">
                  {m.last_sync_at
                    ? `synced ${formatAgo(m.last_sync_at)}`
                    : 'never synced'}
                </div>
                {m.role !== 'owner' && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="ml-auto text-[var(--color-destructive)] hover:text-[var(--color-destructive)] sm:ml-0"
                  >
                    Remove
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </GlassCard>
      </PlanGate>

      <Dialog open={inviteOpen} onOpenChange={setInviteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Invite a teammate</DialogTitle>
            <DialogDescription>
              They&apos;ll get an email with a sign-up link scoped to this workspace.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 pt-2">
            {inviteStatus && (
              <p className="rounded-md bg-[rgba(34,197,94,0.1)] px-3 py-2 text-sm text-[var(--color-success)]">
                {inviteStatus}
              </p>
            )}
            <div className="space-y-2">
              <Label htmlFor="inviteEmail">Email</Label>
              <Input id="inviteEmail" type="email" placeholder="teammate@company.com"
                value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="inviteRole">Role</Label>
              <select
                id="inviteRole"
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value as MemberRole)}
                className="w-full rounded-[0.5rem] border border-[var(--color-border)] bg-[rgba(21,29,48,0.6)] px-3 py-2 text-sm"
              >
                <option value="member">Member — see own brain only</option>
                <option value="admin">Admin — manage team + settings</option>
              </select>
            </div>
            <Button
              onClick={handleInvite}
              disabled={inviting || !inviteEmail}
              className="w-full"
            >
              {inviting ? 'Sending…' : 'Send invite'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}

function formatAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime()
  const h = Math.floor(diffMs / 3600_000)
  if (h < 1) return `${Math.floor(diffMs / 60_000)}m ago`
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}
