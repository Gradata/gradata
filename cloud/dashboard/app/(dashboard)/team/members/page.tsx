'use client'

import { useState } from 'react'
import { GlassCard } from '@/components/layout/GlassCard'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from '@/components/ui/dialog'
import { PlanGate, PLANS, type PlanTier } from '@/components/brain/PlanBadge'
import { useApi } from '@/hooks/useApi'
import type { InviteResponse, InviteRole, MemberRole, TeamMember, UserProfile } from '@/types/api'
import { LoadingSpinner } from '@/components/shared/LoadingSpinner'
import { ErrorState } from '@/components/shared/ErrorState'
import api from '@/lib/api'
import { readApiError } from '@/lib/errors'
import { formatSyncAgo, normalizeRole, pickWorkspaceId } from '@/lib/team'

const ROLE_BADGE: Record<MemberRole, string> = {
  owner:  'bg-[rgba(124,58,237,0.12)] text-[var(--color-accent-violet)]',
  admin:  'bg-[rgba(58,130,255,0.12)] text-[var(--color-accent-blue)]',
  member: 'bg-white/[0.06] text-[var(--color-body)]',
}

export default function TeamMembersPage() {
  const {
    data: profile,
    loading: profileLoading,
    error: profileError,
    refetch: refetchProfile,
  } = useApi<UserProfile>('/users/me')
  const workspaceId = pickWorkspaceId(profile?.workspaces)

  const {
    data: members,
    loading: membersLoading,
    error: membersError,
    refetch,
  } = useApi<TeamMember[]>(workspaceId ? `/workspaces/${workspaceId}/members` : null)

  const [inviteOpen, setInviteOpen] = useState(false)
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState<InviteRole>('member')
  const [inviting, setInviting] = useState(false)
  const [inviteStatus, setInviteStatus] = useState<string | null>(null)
  const [inviteError, setInviteError] = useState<string | null>(null)
  // Track busy state per-member so concurrent mutations on different rows
  // don't stomp on each other's loading flags or re-enable controls early.
  const [busyUserIds, setBusyUserIds] = useState<Set<string>>(new Set())
  // Track row errors per user_id so failures on one row aren't cleared by
  // concurrent or subsequent actions on other rows (CR feedback).
  const [rowErrors, setRowErrors] = useState<Record<string, string | null>>({})

  const setRowBusy = (userId: string, busy: boolean) => {
    setBusyUserIds((prev) => {
      const next = new Set(prev)
      if (busy) next.add(userId)
      else next.delete(userId)
      return next
    })
  }

  const setRowErrorFor = (userId: string, message: string | null) => {
    setRowErrors((prev) => {
      const next = { ...prev }
      if (message) next[userId] = message
      else delete next[userId]
      return next
    })
  }

  // Only show the full-page spinner on the initial load. Once data arrives,
  // background refetches after an invite/remove/role-change must not blank
  // the dialog or row context (CR feedback).
  const initialMembersLoad = Boolean(workspaceId) && members === null && !membersError
  if (profileLoading || initialMembersLoad) return <LoadingSpinner className="py-20" />

  if (profileError) return <ErrorState message={profileError} onRetry={refetchProfile} />

  const currentPlan = (profile?.plan?.toLowerCase() ?? 'free') as PlanTier
  const planAllowsInvites =
    (PLANS[currentPlan]?.rank ?? 0) >= PLANS.team.rank

  if (!workspaceId) {
    return (
      <div className="py-12 text-center">
        <h1 className="text-[22px]">Members</h1>
        <p className="mt-3 text-[13px] text-[var(--color-body)]">
          No workspace found for your account yet.
        </p>
      </div>
    )
  }
  if (membersError) return <ErrorState message={membersError} onRetry={refetch} />

  const roster = members ?? []

  const handleInvite = async () => {
    const email = inviteEmail.trim()
    if (!planAllowsInvites) {
      setInviteError('Invites require the Team plan. Upgrade to enable this.')
      return
    }
    if (!email) {
      setInviteError('Enter a valid email address.')
      return
    }
    setInviting(true)
    setInviteError(null)
    setInviteStatus(null)
    try {
      const res = await api.post<InviteResponse>(
        `/workspaces/${workspaceId}/invites`,
        { email, role: inviteRole },
      )
      setInviteStatus(`Invite sent to ${res.data.email}`)
      setInviteEmail('')
      refetch()
    } catch (err) {
      setInviteError(readApiError(err, 'Could not send invite. Try again.'))
    } finally {
      setInviting(false)
    }
  }

  const handleRemove = async (m: TeamMember) => {
    if (!confirm(`Remove ${m.display_name || m.email || m.user_id} from the workspace?`)) return
    setRowBusy(m.user_id, true)
    setRowErrorFor(m.user_id, null)
    try {
      await api.delete(`/workspaces/${workspaceId}/members/${m.user_id}`)
      await refetch()
    } catch (err) {
      setRowErrorFor(m.user_id, readApiError(err, 'Could not remove member.'))
    } finally {
      setRowBusy(m.user_id, false)
    }
  }

  const handleRoleChange = async (m: TeamMember, nextRole: InviteRole) => {
    setRowBusy(m.user_id, true)
    setRowErrorFor(m.user_id, null)
    try {
      await api.patch(`/workspaces/${workspaceId}/members/${m.user_id}`, { role: nextRole })
      await refetch()
    } catch (err) {
      setRowErrorFor(m.user_id, readApiError(err, 'Could not update role.'))
    } finally {
      setRowBusy(m.user_id, false)
    }
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
        <Button onClick={() => { setInviteStatus(null); setInviteError(null); setInviteOpen(true) }}>
          Invite member
        </Button>
      </header>

      <PlanGate current={currentPlan} requires="team" featureName="Team member management">
        <GlassCard gradTop>
          {roster.length === 0 ? (
            <p className="py-6 text-center text-[13px] text-[var(--color-body)]">
              No members yet. Invite your first teammate above.
            </p>
          ) : (
            <ul className="divide-y divide-[var(--color-border)]">
              {roster.map((m) => {
                const role: MemberRole = normalizeRole(m.role)
                const busy = busyUserIds.has(m.user_id)
                const rowError = rowErrors[m.user_id] ?? null
                return (
                  <li
                    key={m.user_id}
                    className="flex flex-col gap-y-1 py-3 first:pt-0 last:pb-0"
                  >
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 sm:flex-nowrap">
                      <div className="min-w-0 flex-1 basis-full sm:basis-auto">
                        <div className="flex flex-wrap items-baseline gap-2.5">
                          <span className="text-[13px] font-medium">
                            {m.display_name || m.email || m.user_id}
                          </span>
                          <span className={`rounded-[0.25rem] px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wider ${ROLE_BADGE[role]}`}>
                            {role}
                          </span>
                        </div>
                        <div className="font-mono text-[10px] text-[var(--color-body)] truncate">
                          {m.email || '—'}
                        </div>
                      </div>
                      <div className="font-mono text-[11px] text-[var(--color-body)] sm:w-32 sm:text-right">
                        {formatSyncAgo(m.last_sync_at)}
                      </div>
                      {role !== 'owner' && (
                        <>
                          <select
                            aria-label={`Role for ${m.email ?? m.user_id}`}
                            disabled={busy}
                            value={role === 'admin' ? 'admin' : 'member'}
                            onChange={(e) => handleRoleChange(m, e.target.value as InviteRole)}
                            className="rounded-[0.5rem] border border-[var(--color-border)] bg-[rgba(21,29,48,0.6)] px-2 py-1 text-xs"
                          >
                            <option value="member">member</option>
                            <option value="admin">admin</option>
                          </select>
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={busy}
                            onClick={() => handleRemove(m)}
                            className="text-[var(--color-destructive)] hover:text-[var(--color-destructive)]"
                          >
                            {busy ? '…' : 'Remove'}
                          </Button>
                        </>
                      )}
                    </div>
                    {rowError && (
                      <div
                        role="alert"
                        className="ml-0 mt-1 rounded-md border border-[var(--color-destructive)]/30 bg-[var(--color-destructive)]/10 px-3 py-1.5 text-[12px] text-[var(--color-destructive)]"
                      >
                        {rowError}
                      </div>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
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
            {inviteError && (
              <p className="rounded-md border border-[var(--color-destructive)]/30 bg-[var(--color-destructive)]/10 px-3 py-2 text-sm text-[var(--color-destructive)]">
                {inviteError}
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
                onChange={(e) => setInviteRole(e.target.value as InviteRole)}
                className="w-full rounded-[0.5rem] border border-[var(--color-border)] bg-[rgba(21,29,48,0.6)] px-3 py-2 text-sm"
              >
                <option value="member">Member — see own brain only</option>
                <option value="admin">Admin — manage team + settings</option>
              </select>
            </div>
            <Button
              onClick={handleInvite}
              disabled={inviting || !inviteEmail.trim()}
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
